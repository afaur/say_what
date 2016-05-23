import requests
from requests.auth import HTTPBasicAuth
import time
import json
import subprocess

requests.packages.urllib3.disable_warnings()

SPLUNK_URL = 'https://localhost:8089'
CREDS = ('username', 'password')

# Hipchat creds and my user id
hipchat_url = "https://hipchat.company.com"
hipchat_auth_token = ""
hipchat_user_id = 1

name = "josh"

# Check for mentions within the last minute
name_search = ("""search index=say_what sourcetype=_json """
               """minutes=*{}* earliest=-1m@s""".format(name))

# Get everything that was said in the last minute
minutes_search = ("""search index=say_what sourcetype=_json """
                  """minutes=* earliest=-1m@s| sort _time| fields minutes""")


def start_splunk_search(search_string):
    try:
        r = requests.post(
            '%s/services/search/jobs' % SPLUNK_URL,
            data={"search": search_string},
            auth=HTTPBasicAuth(*CREDS),
            verify=False,
            params={'output_mode': 'json'})
        sid = r.json()['sid']
        return sid
    except Exception, e:
        print e


def search_results(sid):
    done = False
    print "Searching Splunk"
    while done is False:
        status = requests.get(
            '%s/services/search/jobs/%s' % (SPLUNK_URL, sid),
            auth=HTTPBasicAuth(*CREDS),
            verify=False,
            params={'output_mode': 'json'}
        )

        done = status.json()['entry'][0]['content']['isDone']
        time.sleep(1)

    result_count = int(status.json()['entry'][0]['content']['resultCount'])
    return result_count


def get_results(sid, result_count):
    events = []
    offset = 0

    while result_count > len(events):
        offset = len(events)
        results = requests.get(
            '%s/services/search/jobs/%s/results/' % (SPLUNK_URL, sid),
            auth=HTTPBasicAuth(*CREDS),
            verify=False,
            params={
                'output_mode': 'json',
                'count': 0, 'f': 'minutes',
                'offset': offset
            })

        more_events = [
            row['minutes']
            .encode('utf-8') for row in results.json()['results']
        ]
        events += more_events
    return events


def splunk_search(search_string):
    search_id = start_splunk_search(search_string)
    search_result_count = search_results(search_id)
    events = get_results(search_id, search_result_count)
    # print "Splunk returned {} events".format(search_result_count)
    return events


def notify(user_id, auth_token, message):
    # Send the conversation context to yourself on hipchat
    data = {
        'message': message,
        'notify': True,
        'message_format': 'text'
    }

    data = json.dumps(data)

    requests.post(
        '{}/v2/user/{}/message'.format(hipchat_url, user_id),
        data=data,
        headers={
            'content-type': 'application/json',
            "Authorization": "Bearer {}".format(auth_token)
        }
    )


def muted():
    # Play the "Sorry, I was on mute" audio file.
    audio_file = "./Muted.m4a"
    # This works on my macbook,
    # change the command line tool to another one if on a different OS
    subprocess.call(["afplay", audio_file])

while True:
    mentioned = splunk_search(name_search)
    if len(mentioned) == 0:
        time.sleep(1)
        continue
    mention_time = time.time()
    print "You were mentioned!"
    minutes = splunk_search(minutes_search)
    try:
        minutes = "\n".join(minutes)
        notify(hipchat_user_id, hipchat_auth_token, minutes)
    except Exception as e:
        print e

    while int(time.time() - mention_time) < 15:
        time.sleep(1)

    muted()

    # Wait another minute before checking for name mentions
    time.sleep(60)

