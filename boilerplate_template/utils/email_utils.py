# utils/email_utils.py

import smtplib
from email.mime.text import MIMEText
import logging

def send_mail(to, subject, text, area_set, send_emails): # no default so we don't silently fail =False):
    """Send an email with optional area_set prefix. Skip if send_emails is False."""
    if not send_emails:
        print("Email sending is disabled. Skipping email.")
        return

    try:
        prefix = f"Area set: {area_set} " if area_set else ""
        print(f"Sending email: {prefix}{subject}")
        
        if not isinstance(text, str):
            text = str(text)

        msg = MIMEText(text)
        msg['Subject'] = f"{prefix}{subject}"
        msg['From'] = 'johnnygooddeals@gmail.com'
        msg['To'] = to

        with smtplib.SMTP_SSL("smtp.gmail.com") as s:
            s.login('johnnygooddeals@gmail.com', 'vdzsukbhxjcqelej')
            s.send_message(msg)

    except Exception as e:
        logging.error(f"Failed to send email to {to}: {e}")

def handle_error(function_name, error_msg, area=None, url=None, deltaT=None, area_set=None, send_emails=False):
    """Logs and optionally emails the error with details."""
    error_message = (
        f"Error in {function_name}: {error_msg}\n"
        f"for area {area}, url: {url}, running time {deltaT}"
    )
    print(error_message)
    logging.error(error_message)

    send_mail(
        to='douglasemckinley@gmail.com',
        subject=f"Error in {function_name} for area {area}",
        text=error_message,
        area_set=area_set,
        send_emails=send_emails
    )
