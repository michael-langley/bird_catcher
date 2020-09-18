import logging
import base64
import os
import json
from google.auth.transport import requests
from google.oauth2 import service_account
from google.cloud.functions.context import Context
from google.cloud.pubsub_v1 import PublisherClient
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
from typing import Dict, Any
from typing_extensions import TypedDict

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def get_session():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    creds = os.path.join(
        current_dir, f"{os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')}"
    )

    service_account_json = json.loads(open(creds).read())

    scoped_credentials = service_account.Credentials.from_service_account_info(
        service_account_json,
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )
    retry_strategy = Retry(
        total=3,
        status_forcelist=[429, 500, 502, 503, 504],
        method_whitelist=["HEAD", "GET", "OPTIONS"],
        backoff_factor=1,
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session = requests.AuthorizedSession(scoped_credentials)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def publish_message(response_text, patient_id, event_attributes):
    publisher = PublisherClient()

    # pylint: disable=no-member
    topic_path = publisher.topic_path(
        os.environ.get("PROJECT_NAME"), os.environ.get("TOPIC_NAME")
    )
    data = response_text.encode("utf-8")
    future = publisher.publish(
        topic_path,
        data=data,
        **event_attributes,
        patient_id=patient_id,
    )
    message_id = future.result()
    logger.info(f"Successfully published message: {message_id}")
    print(f"Successfully published message: {message_id}")


class PubSubMessage(TypedDict):
    data: str
    attributes: Dict[str, Any]


def bird_catcher(event: PubSubMessage, context: Context):

    if not "data" in event:
        logger.error(f"No Data key found for message")
        return None

    try:
        message_path = base64.b64decode(event["data"]).decode("utf-8")
        logger.info(
            f"Message Received by Bird Catcher: {message_path} : {event['attributes']}"
        )
        session = get_session()
        response = session.get(f"https://healthcare.googleapis.com/v1/{message_path}")
        response.raise_for_status()
        resource = response.json()
        if event["attributes"]["resourceType"] == "Patient":
            split_url = message_path.split("/")
            patient_id = split_url[-1]
        elif "subject" not in resource:
            logger.error(f"No Subject found for resource: {resource}")
            return None
        else:
            reference = resource["subject"]["reference"]
            patient_id = reference.split("/")[-1]

        publish_message(response.text, patient_id, event["attributes"])
    except Exception as ex:
        logger.error(f"Error getting message details from Fhir Store: {ex}")
