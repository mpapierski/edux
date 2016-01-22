from bs4 import BeautifulSoup


def extract_courses(fileobj):
    '''Extracts all courses.

    Returns list of pairs (name, url)
    '''
    bs = BeautifulSoup(fileobj.read(), 'html.parser')
    courses = bs.select('#ctl00_ContentPlaceHolder1_grdKursy_ctl00 tbody')[0]
    for tr in courses.select('tr'):
        a = tr.select('a')[0]
        yield (a['title'], a['href'])


def main():
    with open('/Users/michal/Downloads/edux/Premain.aspx.html') as fileobj:
        extract_courses(fileobj)

if __name__ == '__main__':
    main()
