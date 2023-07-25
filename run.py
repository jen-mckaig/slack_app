import argparse
import logging
import logging.config
import os
import time
from datetime import datetime, timedelta

import yaml
from flask import Flask
from flask_apscheduler import APScheduler
from slack_bolt.adapter.socket_mode import SocketModeHandler
from waitress import serve
from werkzeug.middleware.dispatcher import DispatcherMiddleware

from scripts.background.meta_process import MetaProcess
from scripts.background.user_notifications import CompletedTicketNotifier
from scripts.common.constants import DateTimeFormats
from scripts.common.notion import NotionConnector, NotionSourceConfig
from scripts.common.s3 import S3BucketConnector
from scripts.common.slack import SlackConnector, SlackSourceConfig

# Parsing YAML file
parser = argparse.ArgumentParser(description="Running the Slack ticketbot")
parser.add_argument("config", help="A configuration file in YAML format.")
args = parser.parse_args()
config = yaml.safe_load(open(args.config))

# Configure logging
log_config = config["logging"]
logging.config.dictConfig(log_config)
logger = logging.getLogger(__name__)

# Instantiate the Slack Connector
slack_config = config["slack"]
slack_messages = slack_config["slack_messages"]
slash_command = slack_config["slash_command"]
slack_args = SlackSourceConfig(**slack_config["slack_args"])

slack_conn = SlackConnector(
    bot_token=slack_config["bot_token"],
    signing_secret=slack_config["signing_secret"],
    slack_args=slack_args,
)

# Instantiate the Notion Connector
notion_config = config["notion"]
notion_args = NotionSourceConfig(**notion_config["notion_args"])
notion_conn = NotionConnector(
    notion_pages_endpoint=notion_config["pages_endpoint"],
    notion_database_endpoint=notion_config["db_endpoint"],
    notion_token=notion_config["token"],
    notion_database_id=notion_config["database_id"],
    notion_args=notion_args,
)

# Instantiate the AWS S3 Connector
s3_config = config["s3"]
s3_conn = S3BucketConnector(
    access_key=s3_config["access_key"],
    secret_key=s3_config["secret_key"],
    endpoint_url=s3_config["endpoint_url"],
    bucket=s3_config["bucket"],
)


@slack_conn._slack_app.command(slash_command)
def open_ticket(ack: callable, command: dict):
    ack()

    trigger = command["trigger_id"]
    form = slack_conn.build_form_view()
    slack_conn.open_form_view(trigger_id=trigger, form_view=form)


@slack_conn._slack_app.view("form_1")
def handle_submission(ack: callable, body: dict):
    ack()

    team_id = os.environ[slack_config["team_channel_id"]]
    user_id, ticket = slack_conn.get_submitted_data(submission_body=body)
    user_success_msg = f"<@{user_id}> {slack_messages['success_msg_user']}"
    team_success_msg = f"{slack_messages['success_msg_team']} <@{user_id}>"
    user_fail_msg = f"{slack_messages['fail_msg_user']}"
    team_fail_msg = f"{slack_messages['fail_msg_team']} <@{user_id}>"

    status_code = notion_conn.post_object(ticket)

    if status_code != 200:
        time.sleep(3)
        new_status_code = notion_conn.post_object(ticket)
        if new_status_code == 200:
            usr_msg = user_success_msg
            tm_msg = team_success_msg
        else:
            usr_msg = user_fail_msg
            tm_msg = team_fail_msg
    else:
        usr_msg = user_success_msg
        tm_msg = team_success_msg

    slack_conn.post_message(slack_id=user_id, msg=usr_msg)
    slack_conn.post_message(slack_id=team_id, msg=tm_msg)


# Wrap ticket notifier & metafile process in a function to load into the Flask config
def background_jobs():
    ticket_notifier = CompletedTicketNotifier(
        notion=notion_conn,
        slack=slack_conn,
        slack_channel=os.environ[slack_config["team_channel_id"]],
        s3=s3_conn,
    )
    # send notifications
    ticket_notifier.notify()

    # S3 file cleanup date - delete anything older than yesterday
    yesterday = (datetime.today().date() - timedelta(days=1)).strftime(
        DateTimeFormats.datetime_format.value
    )
    # delete old notification logs
    MetaProcess.delete_meta_files(
        s3_bucket_meta=s3_conn, prefix=s3_config['notifications_log_prefix'], date_threshold=yesterday
    )
    # generate updated metafile
    metafile = MetaProcess.generate_meta_file(notion_meta=notion_conn)
    # load updated metafile
    MetaProcess.load_meta_file(
        s3_bucket_meta=s3_conn, meta_file=metafile, prefix=s3_config['metafile_prefix']
    )
    # delete old metafiles
    MetaProcess.delete_meta_files(
        s3_bucket_meta=s3_conn, prefix=s3_config['metafile_prefix'], date_threshold=yesterday
    )


if __name__ == "__main__":
    # Config class for the Flask app and scheduler
    class Config:
        JOBS = [
            {
                "id": "notifications",
                "func": background_jobs,
                "trigger": "interval",
                "minutes": 10,
            }
        ]
        SCHEDULER_API_ENABLED = True

    handler = SocketModeHandler(
        slack_conn._slack_app, os.environ[slack_config["app_token"]]
    )

    # Instantiate and configure Flask app scheduler
    flask_app = Flask(__name__)
    flask_app.config.from_object(Config())
    scheduler = APScheduler()
    scheduler.init_app(flask_app)
    scheduler.start()

    # Middleware app dispatcher to run scripts simultaneously
    application = DispatcherMiddleware(handler.start(), {"/backend": flask_app})
    # Waitress server for production environ
    serve(application, host="0.0.0.0", port=8080)
