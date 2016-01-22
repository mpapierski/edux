import os
import re
import sys
from StringIO import StringIO
from datetime import datetime

import requests
from bs4 import BeautifulSoup


s = requests.Session()


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


def extract_courses(fileobj):
    '''Extracts all courses.

    Returns list of pairs (name, url)
    '''
    bs = BeautifulSoup(fileobj.read(), 'html.parser')
    courses = bs.select('#ctl00_ContentPlaceHolder1_grdKursy_ctl00 tbody')[0]
    for tr in courses.select('tr'):
        a = tr.select('a')[0]
        (course_id, ) = re.findall(
            r'req\.aspx\?id=(\d+)$', a['href'])
        course_id = int(course_id)
        url = 'https://edux.pjwstk.edu.pl/' + a['href']
        yield (course_id, a['title'], url)


def extract_announcements(fileobj):
    '''Extracts all announcements

    Returns list of pairs (timestmap, message)
    '''
    bs = BeautifulSoup(fileobj.read(), 'html.parser')
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


def get_announcements(url):
    '''Gets all announcements
    '''
    r = s.get('https://edux.pjwstk.edu.pl/Announcements.aspx')
    r.raise_for_status()
    with open('Course.html', 'w') as fileobj:
        fileobj.write(r.content)
    fileobj = StringIO(r.content)

    for (timestamp, message) in extract_announcements(fileobj):
        print '---'
        print timestamp
        print message


def get_courses():
    '''Navigates to Premain

    Gets all courses
    '''
    r = s.get('https://edux.pjwstk.edu.pl/Premain.aspx')
    r.raise_for_status()
    fileobj = StringIO(r.content)
    for (course_id, name, url) in extract_courses(fileobj):
        # Get inside the course
        r = s.get(url)
        r.raise_for_status()
        # Get announcement for this course
        get_announcements(url)


def main():
    try:
        print 'login'
        login(os.environ['EDUX_USERNAME'], os.environ['EDUX_PASSWORD'])
    except LoginError as e:
        sys.stderr.write(u'LoginError({})\n'.format(e))
    else:
        get_courses()
    finally:
        print 'logout'


if __name__ == '__main__':
    main()
