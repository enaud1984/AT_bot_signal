import json
from datetime import datetime

import boto3


# Creazione del client SNS
sns_client = boto3.client('sns', region_name='eu-north-1')

# ARN del topic SNS
topic_arn_email = 'arn:aws:sns:eu-north-1:043309340784:Notifiche'
topic_arn_sms = 'arn:aws:sns:eu-north-1:043309340784:notifiche-push'

def sendNotify(message):
    try:
        dt = datetime.now()
        dt = dt.replace(microsecond=0)
        message = f'{dt}\t{json.dumps(message)}'
        # Pubblicazione del messaggio
        response = sns_client.publish(
            TopicArn=topic_arn_email,
            Message=message,
            Subject='Notifica at_bot'
        )
        response_sms = sns_client.publish(
            TopicArn=topic_arn_sms,
            Message=message,
            Subject='Notifica at_bot'
        )

    except Exception as e:
        print('Errore invio Notifiche')