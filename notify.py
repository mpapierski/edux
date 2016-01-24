import os

import requests


key = os.environ['MAILGUN_APIKEY']
domain = os.environ['MAILGUN_DOMAIN']


def send_email(sender, recipient, subject, text):
    request_url = 'https://api.mailgun.net/v2/{}/messages'.format(domain)
    r = requests.post(request_url, auth=('api', key), data={
        'from': sender,
        'to': recipient,
        'subject': subject,
        'text': text
    })
    print 'Status: {0}'.format(r.status_code)
    print 'Body:   {0}'.format(r.text)
    r.raise_for_status()
