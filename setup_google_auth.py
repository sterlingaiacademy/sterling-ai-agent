from google_auth_oauthlib.flow import InstalledAppFlow
import json, os

SCOPES = [
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/calendar',
]

if not os.path.exists('credentials.json'):
    print('credentials.json not found!')
    print('Go to https://console.cloud.google.com')
    print('Create OAuth 2.0 credentials, download as credentials.json')
else:
    flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
    creds = flow.run_local_server(port=0)
    with open('token.json', 'w') as f:
        f.write(creds.to_json())
    print('token.json saved!')
