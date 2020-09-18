from concurrent.futures import TimeoutError
from google.cloud import pubsub_v1
from settings import PROJECT_NAME, SUBSCRIPTION_NAME

timeout = 300.0
subscriber: pubsub_v1.SubscriberClient = pubsub_v1.SubscriberClient()
subscription_path = subscriber.subscription_path(PROJECT_NAME, SUBSCRIPTION_NAME)


def callback(message):
    print(f"{SUBSCRIPTION_NAME} Message Received {message}")
    message.ack()


streaming_pull_future = subscriber.subscribe(subscription_path, callback=callback)
print(f"Listening for messages on {subscription_path}...")

try:
    streaming_pull_future.result(timeout=timeout)
except TimeoutError:
    streaming_pull_future.cancel()
