# -*- encoding: utf-8 -*-
#
# Usage: python edux.py
#
# Michal Papierski <michal@papierski.net>
#
import os
import re
import sys
import operator
from datetime import datetime

import requests
from bs4 import BeautifulSoup

from database import Session, Course, Announcement, Quiz, Folder
from notify import send_email

s = requests.Session()


AIRPLANE_MODE = os.getenv('AIRPLANE_MODE')
EMAIL_SENDER = os.environ['EMAIL_SENDER']
EMAIL_RECIPIENT = os.environ['EMAIL_RECIPIENT']


def send_notify(subject, body):
    '''Send notification
    '''
    if not body:
        return
    if AIRPLANE_MODE:
        sys.stdout.write(u'Subject: {0}\n'.format(subject))
        sys.stdout.write(u'Body: {0}\n'.format(body))
    else:
        send_email(EMAIL_SENDER, EMAIL_RECIPIENT, subject, body)


class LoginError(Exception):

    '''Unable to login'''


def get_form_events(bs):
    '''Extracts meta vars in form...

    Because they use ASP.NET so its not that easy to make a
    POST requests.
    '''
    # This is all we care about
    events = [
        '__EVENTTARGET',
        '__EVENTARGUMENT',
        '__VIEWSTATE',
        '__EVENTVALIDATION',
        '__VIEWSTATEGENERATOR'
    ]
    event = {}
    for e in events:
        css = 'input#{0}'.format(e)
        l = bs.select(css)
        try:
            event[e] = l[0]['value']
        except IndexError:
            pass

    return event


def extract_courses(content):
    '''Extracts all courses.

    Returns list of pairs (name, url)
    '''
    bs = BeautifulSoup(content, 'html.parser')
    courses = bs.select('#ctl00_ContentPlaceHolder1_grdKursy_ctl00 tbody')[0]
    for tr in courses.select('tr'):
        a = tr.select('a')[0]
        # This course id is useful for our internal database
        # so we dont have to force course title to be our primary
        # key, or make any artificial primary key.
        (course_id, ) = re.findall(
            r'req\.aspx\?id=(\d+)$', a['href'])
        course_id = int(course_id)
        url = 'https://edux.pjwstk.edu.pl/' + a['href']
        yield (course_id, a['title'], url)


def extract_announcements(content):
    '''Extracts all announcements

    Returns list of pairs (timestmap, message)
    '''
    bs = BeautifulSoup(content, 'html.parser')
    try:
        announcements = bs.select(
            '#ctl00_ContentPlaceHolder1_grdOgloszenia_ctl00 tbody')[0]
    except IndexError:
        return []

    result = []

    for announcement in announcements.select('tr'):
        (timestamp, message, ) = announcement.select('td')
        # This will convert the timestamp string to a python date.
        # I am almost sure they output the timestamps already shifted
        # with local timezone (because timezones are hard man)
        # TODO: Make it UTC datetime like this: YYYY-MM-DD 00:00:00+00
        timestamp = datetime.strptime(timestamp.text, '%Y-%m-%d').date()
        # BeautifulSoup extracts HTML tags and this text looks ugly and has
        # alot of white chars. This strips them to a single white char.
        message = re.sub(r'\s+', ' ', message.text)
        result.append((timestamp, message))

    # XXX: For some reason I reverse the list and I dont need to do this
    return reversed(result)


def extract_quiz(content):
    '''Extracts all quiz
    '''
    bs = BeautifulSoup(content, 'html.parser')
    try:
        tbody = bs.select(
            '#ctl00_ContentPlaceHolder1_QuizyRadGrid_ctl00 tbody')[0]
    except IndexError:
        return
    for tr in tbody.select('tr'):
        (td1, td2, td3, td4, td5, td6, td7) = tr.select('td')
        quiz_id = int(td1.text.strip())
        # td2 is unkown value
        title = td3.text.strip()
        try:
            start_at = datetime.strptime(td4.text.strip(), '%Y-%m-%d').date()
        except ValueError:
            start_at = None

        try:
            finish_at = datetime.strptime(td5.text.strip(), '%Y-%m-%d').date()
        except ValueError:
            finish_at = None

        duration = td6.text.strip()
        score = td7.text.strip()

        yield (quiz_id, title, start_at, finish_at, duration, score)


def extract_folders(content):
    '''Extracts folders
    '''
    bs = BeautifulSoup(content, 'html.parser')
    try:
        tbody = bs.select(
            '#ctl00_ContentPlaceHolder1_grdFolder_ctl00 tbody')[0]
    except IndexError:
        return
    for tr in tbody.select('tr'):
        (td1, td2, td3, td4) = tr.select('td')
        folder_id = int(td1.text.strip())
        title = td2.text.strip()
        try:
            start_at = datetime.strptime(td3.text.strip(), '%Y-%m-%d').date()
        except ValueError:
            start_at = None

        try:
            finish_at = datetime.strptime(td4.text.strip(), '%Y-%m-%d').date()
        except ValueError:
            finish_at = None

        yield (folder_id, title, start_at, finish_at)


def login(username, password):
    '''Logs in to the edux website
    '''
    url = 'https://edux.pjwstk.edu.pl/Login.aspx'
    r = s.get(url)
    r.raise_for_status()
    bs = BeautifulSoup(r.content, 'html.parser')
    form = get_form_events(bs)
    # ASP.NET serious stuff here
    form['ctl00$ContentPlaceHolder1$Login1$LoginButton'] = 'Zaloguj'
    form['ctl00$ContentPlaceHolder1$Login1$UserName'] = username
    form['ctl00$ContentPlaceHolder1$Login1$Password'] = password
    form['ctl00_RadScriptManager1_TSM'] = ''
    r = s.post(url, data=form)
    r.raise_for_status()

    # Find error
    bs = BeautifulSoup(r.content, 'html.parser')

    try:
        # Much html5 here... many wow...
        font = bs.select(
            '#ctl00_ContentPlaceHolder1_Login1 tr td table font[color=Red]')[0]
        error = font.text.strip()
        if error:
            raise LoginError(error)
    except IndexError:
        pass


def logout():
    '''Logout from edux.

    This makes those ASP.NET admins happy right? No more dead sessions in
    the expensive MSSQL database?
    '''
    r = s.get('https://edux.pjwstk.edu.pl/Logout.aspx')
    r.raise_for_status()


def get_announcements(course, url):
    '''Gets all new announcements

    Returns a list of all new announcements.
    '''
    session = Session()
    try:
        r = s.get('https://edux.pjwstk.edu.pl/Announcements.aspx', stream=True)
        r.raise_for_status()
        new_announcements = extract_announcements(r.content)
        # All pairs of (timestamp, message) are saved to db
        # if they arent there already
        for (timestamp, message) in new_announcements:
            announcement = session.query(Announcement). \
                filter_by(course=course,
                          created_at=timestamp,
                          message=message). \
                first()
            if announcement is None:
                # This is what we care about
                announcement = Announcement(
                    course=course,
                    created_at=timestamp,
                    message=message)
                session.add(announcement)
                print 'New announcement at {0}'.format(timestamp)
                yield (timestamp, message)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_folders(course):
    '''Gets all folders
    '''
    session = Session()
    try:
        r = s.get('https://edux.pjwstk.edu.pl/Folder.aspx')
        r.raise_for_status()
        new_folders = extract_folders(r.content)
        for (folder_id, title, start_at, finish_at) in new_folders:
            folder = session.query(Folder). \
                filter_by(folder_id=folder_id). \
                first()
            if folder is None:
                folder = Folder(
                    folder_id=folder_id,
                    course=course,
                    title=title,
                    start_at=start_at,
                    finish_at=finish_at)
                send_notify('New folder "{}" at {}'.format(title,
                                                           course.title),
                            '''Folder title: {0.title}
Start at: {0.start_at}
Finish at: {0.finish_at}'''.format(folder))

                session.add(folder)
            if (folder.title != title or
                    folder.start_at != start_at or
                    folder.finish_at != finish_at):
                new = {
                    'title': title,
                    'start_at': start_at,
                    'finish_at': finish_at
                }
                send_notify('Folder "{0}" updated'.format(title),
                            '''Folder title: {new[title]} (old: {0.title})
Start at: {new[start_at]} (old: {0.start_at})
Finish at: {new[finish_at]} (old: {0.finish_at})'''.format(folder,
                                                           new=new))

                folder.title = title
                folder.start_at = start_at
                folder.finish_at = finish_at
                session.add(folder)
        session.commit()
    finally:
        session.close()


def get_quiz(course):
    '''Navigates to quiz

    Gets all quiz
    '''
    session = Session()
    try:
        r = s.get('https://edux.pjwstk.edu.pl/Quiz.aspx')
        r.raise_for_status()

        # quiz = []

        for (quiz_id,
             title,
             start_at,
             finish_at,
             duration,
             score) in extract_quiz(r.content):
            quiz = session.query(Quiz). \
                filter_by(quiz_id=quiz_id). \
                first()
            if quiz is None:
                quiz = Quiz(
                    course=course,
                    quiz_id=quiz_id,
                    title=title,
                    start_at=start_at,
                    finish_at=finish_at,
                    duration=duration,
                    score=score
                )
                session.add(quiz)
                print u'New quiz "{0}" {1} - {2}'.format(
                    quiz.title,
                    quiz.start_at,
                    quiz.finish_at)
                send_notify(u'Quiz "{0.title}" at {1.title}'.format(quiz,
                                                                    course),
                            u'''Quiz title: {0.title}
Course: {1.title}
Start: {0.start_at}
Finish: {0.finish_at}
Duration: {0.duration}
Score: {0.score}
'''.format(quiz, course))

            if (quiz.title != title or
                    quiz.start_at != start_at or
                    quiz.finish_at != finish_at or
                    quiz.duration != duration or
                    quiz.score != score):
                send_notify(u'Quiz "{0.title}" changed'.format(quiz,
                                                               course),
                            u'''Quiz title: {new[title]} (old: {0.title})
Course: {1.title}
Start: {new[start_at]} (old: {0.start_at})
Finish: {new[finish_at]} (old: {0.finish_at})
Duration: {new[duration]} (old: {0.duration})
Score: {new[score]} (old: {0.score})
'''.format(quiz, course, new={'title': title,
                              'start_at': start_at,
                              'finish_at': finish_at,
                              'duration': duration,
                              'score': score}))
                quiz.title = title
                quiz.start_at = start_at
                quiz.finish_at = finish_at
                quiz.duration = duration
                quiz.score = score
                session.add(quiz)

        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_courses():
    '''Navigates to Premain

    Gets all courses
    '''
    session = Session()
    r = s.get('https://edux.pjwstk.edu.pl/Premain.aspx')
    r.raise_for_status()

    new_announcements = []

    for (course_id, name, url) in extract_courses(r.content):
        course = session.query(Course). \
            filter_by(course_id=course_id). \
            first()
        if course is None:
            print 'Add new course "{}"'.format(name)
            course = Course(
                course_id=course_id,
                title=name)
            session.add(course)
        print course.title
        # Get inside the course
        r = s.get(url)
        r.raise_for_status()
        session.expunge(course)
        # Get announcement for this course
        for (timestamp, announcement) in get_announcements(course, url):
            new_announcements.append((course.title, timestamp, announcement))

        get_quiz(course)
        get_folders(course)

    # Prepare email stuff from gathered data

    subject = 'You have {0} new announcements on EDUX'.format(
        len(new_announcements))

    body = u''

    # Sort new announcements so highest date (newer) will be on top
    sorted_announcements = sorted(new_announcements,
                                  key=operator.itemgetter(1),
                                  reverse=True)
    # TODO: Use some templating here
    for i, (course, timestamp, announcement) in enumerate(sorted_announcements,
                                                          1):
        body += u'{0}. {1} at {2}\n{3}\n\n'.format(
            i,
            timestamp,
            course,
            announcement)

    # Cant send empty body because mailgun throws HTTP400s.
    send_notify(subject, body)

    session.commit()


def main():
    try:
        login(os.environ['EDUX_USERNAME'], os.environ['EDUX_PASSWORD'])
    except LoginError as e:
        sys.stderr.write(u'LoginError({})\n'.format(e))
        return
    try:
        get_courses()
    finally:
        logout()


if __name__ == '__main__':
    main()
