# RedAlertSpecificTown
python script that runs every 15 seconds to notify upon an expected Alarm

the following commands will create a docker to run the red_alert.py script

First, build the Docker from the repo's folder:

docker build --network host -t red-alert-israel .

To run the Docker:
docker run -e GOOGLE_WEBHOOK_URL="https://script.google.com/macros/s/[YOUR_DEPLOYMENT_ID] -e TELEGRAM_BOT_TOKEN="[TELEGRAM_TOKEN]" -e TELEGRAM_CHAT_ID="[CHAT_ID]" -d --network host --name red-alert --restart always red-alert-israel

**nOTE DUE TO LIMITATIONS OF BEZEQ CLOUD I HAD TO RUN AS --NETWORK HOST
