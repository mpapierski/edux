import os
import re
import sys
import operator
from datetime import datetime

import requests
from bs4 import BeautifulSoup

from database import Session, Course, Announcement
from notify import send_email

s = requests.Session()


EMAIL_SENDER = os.environ['EMAIL_SENDER']
EMAIL_RECIPIENT = os.environ['EMAIL_RECIPIENT']


class LoginError(Exception):
    '''Unable to login'''


def get_form_events(bs):
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
    announcements = bs.select(
        '#ctl00_ContentPlaceHolder1_grdOgloszenia_ctl00 tbody')[0]

    result = []

    for announcement in announcements.select('tr'):
        (timestamp, message, ) = announcement.select('td')
        timestamp = datetime.strptime(timestamp.text, '%Y-%m-%d').date()
        message = re.sub(r'\s+', ' ', message.text)
        result.append((timestamp, message))
    return reversed(result)


def login(username, password):
    '''Logs in to the edux website
    '''
    url = 'https://edux.pjwstk.edu.pl/Login.aspx'
    r = s.get(url)
    r.raise_for_status()
    bs = BeautifulSoup(r.content, 'html.parser')
    form = get_form_events(bs)
    form['ctl00$ContentPlaceHolder1$Login1$LoginButton'] = 'Zaloguj'
    form['ctl00$ContentPlaceHolder1$Login1$UserName'] = username
    form['ctl00$ContentPlaceHolder1$Login1$Password'] = password
    form['ctl00_RadScriptManager1_TSM'] = ''
    r = s.post(url, data=form)
    r.raise_for_status()

    # Find error
    bs = BeautifulSoup(r.content, 'html.parser')

    try:
        font = bs.select(
            '#ctl00_ContentPlaceHolder1_Login1 tr td table font[color=Red]')[0]
        error = font.text.strip()
        if error:
            raise LoginError(error)
    except IndexError:
        pass


def logout():
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

    subject = 'You have {0} new announcements on EDUX'.format(
        len(new_announcements))

    body = u''

    # Sort new announcements so highest date (newer) will be on top
    sorted_announcements = sorted(new_announcements,
                                  key=operator.itemgetter(1),
                                  reverse=True)
    for i, (course, timestamp, announcement) in enumerate(sorted_announcements,
                                                          1):
        body += u'{0}. {1} at {2}\n{3}\n\n'.format(
            i,
            timestamp,
            course,
            announcement)

    if body:
        send_email(EMAIL_SENDER, EMAIL_RECIPIENT, subject, body)

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
