from django.shortcuts import render


import httplib2
import os

from apiclient import discovery
import oauth2client
from oauth2client import client
from oauth2client import tools

import datetime

try:
    import argparse
    flags = tools.argparser.parse_args([])

    # flags = argparse.ArgumentParser(parents=[tools.argparser]).parse_args()
except ImportError:
    flags = None

# If modifying these scopes, delete your previously saved credentials
# at ~/.credentials/calendar-python-quickstart.json
SCOPES = 'https://www.googleapis.com/auth/calendar'
CLIENT_SECRET_FILE = 'client_secret.json'
APPLICATION_NAME = 'Google Calendar API Python Quickstart'

class GCalAPI(object):

    service = None

    def __init__(self):
        credentials = self.get_credentials()
        http = credentials.authorize(httplib2.Http())
        self.service = discovery.build('calendar', 'v3', http=http)

        # Testing
        # self.api_list_calendar('primary')
        # self.api_add_event()
        # self.list_accesible_calendars()
        # self.api_list_calendar('sangsta@dropbox.com')
        # self.list_availabilities_for_user_for_day('jlee@dropbox.com', None)
        # self.list_availabilities_for_day(['jlee@dropbox.com', 'sangsta@dropbox.com'])
        # self.find_group_meeting("",['jlee@dropbox.com', 'sangsta@dropbox.com'], 3, "", "")

    def get_credentials(self):
        """Gets valid user credentials from storage.

        If nothing has been stored, or if the stored credentials are invalid,
        the OAuth2 flow is completed to obtain the new credentials.

        Returns:
            Credentials, the obtained credential.
        """
        home_dir = os.path.expanduser('~')
        credential_dir = os.path.join(".", '.credentials')
        if not os.path.exists(credential_dir):
            os.makedirs(credential_dir)
        credential_path = os.path.join(credential_dir,
                                       'calendar-python-quickstart.json')

        store = oauth2client.file.Storage(credential_path)
        credentials = store.get()
        if not credentials or credentials.invalid:
            flow = client.flow_from_clientsecrets(CLIENT_SECRET_FILE, SCOPES)
            flow.user_agent = APPLICATION_NAME
            if flags:
                credentials = tools.run_flow(flow, store, flags)
            else: # Needed only for compatibility with Python 2.6
                credentials = tools.run(flow, store)
            print 'Storing credentials to ' + credential_path
        return credentials

    def find_meeting_time(self, title, participants, num_days, description, location):
        """ Returns top 3 options when you will all be free.
        num_days: Number of days that will be scanned
        """
        top_availabilities = []

        for i in xrange(num_days):
            today = datetime.datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            curr_date = today + datetime.timedelta(hours=24*i)
            free_30_min_slots = self.list_availabilities_for_day(participants, curr_date)

            for i in xrange(len(free_30_min_slots)):
                # Assume 9-5 work day
                if i > 9*2 and i < (12+5)*2 and free_30_min_slots[i]:
                    appt_date = datetime.datetime(2016, curr_date.month, curr_date.day, i/2, 0 if i%2 ==0 else 30)
                    top_availabilities.append(appt_date)

        return top_availabilities

    def schedule_meeting(self, summary, participants, start_date, description, location):
        event = {
          'summary': summary,
          'location': location,
          'description': description,
          'start': {
            'dateTime': '2016-07-26T09:00:00-07:00', #TODO(jlee): Figure out input start_date format
            'timeZone': 'America/Los_Angeles',
          },
          'end': {
            'dateTime': '2016-07-26T17:00:00-07:00', #TODO(jlee): Figure out input start_date format
            'timeZone': 'America/Los_Angeles',
          },
          'attendees': [{'email': p for p in participants}],
          'reminders': {
            'useDefault': True,
          },
        }
        self.api_add_event(event)

    def list_availabilities_for_day(self, participants=[], start_date=None):
        """ Build and availability map for all participants."""
        free_30_min_slots = [True for i in xrange(24*2)]

        for pID in participants:
            participant_avail = self.list_availabilities_for_user_for_day(pID, start_date)
            free_30_min_slots = map(lambda (x,y): x and y, zip(free_30_min_slots, participant_avail))

        return free_30_min_slots

    def list_availabilities_for_user_for_day(self, participantId, start_date=None):
        events = self.api_list_calendar(participantId, start_date)
        if start_date is None:
            start_date = datetime.datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

        date_month = start_date.month
        date_day = start_date.day
        duration_mins = 30
        free_30_min_slots = [True for i in xrange(24*2)]
        has_entries_on_next_day = False if len(events) > 0 else True

        for event in events:
            start = event['start'].get('dateTime')
            end = event['end'].get('dateTime')

            if start is None or end is None:
                continue

            start_time = datetime.datetime.strptime(start[:-6], '%Y-%m-%dT%H:%M:%S')
            end_time = datetime.datetime.strptime(end[:-6], '%Y-%m-%dT%H:%M:%S')
            # Avoid funky edge cases.
            if start_time.day != end_time.day:
                print "Overlapping day events are not supported"
                continue
            if start_time.day != date_day:
                has_entries_on_next_day = True
                continue

            # print "%d/%d %d:%d - %d:%d" % (start_time.month, start_time.day, start_time.hour, start_time.minute, end_time.hour, end_time.minute)
            for hour in xrange(start_time.hour, end_time.hour+1):
                if hour == start_time.hour and start_time.minute >= 30:
                    # Only uses last half of hour
                    free_30_min_slots[hour*2+1] = False
                elif hour == end_time.hour and end_time.minute == 00:
                    continue
                elif hour == end_time.hour and end_time.minute <= 30:
                    # Only uses first half of hour
                    free_30_min_slots[hour*2] = False
                else:
                  free_30_min_slots[hour*2] = False
                  free_30_min_slots[hour*2+1] = False
        # print self._print_free_slots(free_30_min_slots)
        assert has_entries_on_next_day, "Did not scan enough calendar event entries for this day. Increase maxResults."
        return free_30_min_slots

    def _print_free_slots(self, slots):
        print "----- Free slots -----"
        for i in xrange(len(slots)):
            if slots[i] == True:
                print "%s:%s  %s" % (str(i/2), ("00" if i%2==0 else "30"), ("Free" if slots[i] else "Busy"))

    def api_list_calendar(self, calendarId, start_date=None):
        if start_date is None:
            now = datetime.datetime.utcnow().isoformat() + 'Z' # 'Z' indicates UTC time
            timeMin = now
        else:
            timeMin = start_date.isoformat() + 'Z'

        print 'Getting the upcoming events for cal ' + str(calendarId)

        eventsResult = self.service.events().list(
            calendarId=calendarId, timeMin=timeMin, maxResults=40, singleEvents=True,
            orderBy='startTime').execute()
        events = eventsResult.get('items', [])

        if not events:
            print 'No upcoming events found.'
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            print start, event['summary'].encode('ascii', 'ignore') if 'summary' in event else "No summary"

        return events

    def api_add_event(self, new_event=None):
        default_event = {
          'summary': 'Amazing potato test event.',
          'location': '800 Howard St., San Francisco, CA 94103',
          'description': 'A chance to hear more about potato products.',
          'start': {
            'dateTime': '2016-07-26T09:00:00-07:00',
            'timeZone': 'America/Los_Angeles',
          },
          'end': {
            'dateTime': '2016-07-26T17:00:00-07:00',
            'timeZone': 'America/Los_Angeles',
          },
          'recurrence': [
            'RRULE:FREQ=DAILY;COUNT=2'
          ],
          'attendees': [
            # {'email': 'jchao@dropbox.com'},
          ],
          'reminders': {
            'useDefault': False,
            'overrides': [
              {'method': 'email', 'minutes': 24 * 60},
              {'method': 'popup', 'minutes': 10},
            ],
          },
        }

        event = new_event or default_event

        created_event = self.service.events().insert(calendarId='primary', body=event).execute()
        print 'Event created:' + str(created_event.get('htmlLink'))
        eventId = created_event.get('id')
        self.service.events().delete(calendarId='primary', eventId=eventId).execute()
        print 'Event deleted:' + str(created_event.get('htmlLink'))

api = GCalAPI()

# Create your views here.
from django.shortcuts import render
from django.http import HttpResponse
from django.http import JsonResponse

def index(request):
    return HttpResponse("Hello, world.")

def find_meeting_time(request):
    summary = request.GET.get('summary', "No Summary")
    participants = request.GET.getlist('participants', [])
    participants.append("jlee@dropbox.com") # I'm always in the meeting :)
    num_days = int(request.GET.get('num_days', 2))
    description = request.GET.get('description', "No Description")
    location = request.GET.get('location')

    print "Processing %s" % participants
    avails = api.find_meeting_time(
        summary, participants, num_days, description, location)

    return JsonResponse({'meetings':avails})

def schedule_meeting(request):
    return JsonResponse({'status':'ok'})
