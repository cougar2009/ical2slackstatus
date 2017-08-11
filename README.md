# ical2slackstatus
Automatically set your slack status based on the events in your calendar.

## How to get in on the action
### Executive Summary
1. Create a file called <your net id>.yml (use example_config.yml as a guide).
2. Login to prd-appdev-oit-byu
3. Upload your yml file to the ical2slackstatus-prd-configbucket-s3 bucket in s3.

Your slack status will be updated during work hours to what is on
your calendar or a default message if there isn't anything on your calendar at
the time.

### Details
ical2slackstatus is implemented as an AWS Lambda that runs every 15 minutes
during work hours Mon-Fri.  I.e., it will run at 8am, 8:15am, 8:30am, 8:45pm,
9am..., 4:45pm, 5pm, etc.  It looks in the ical2slackstatus-prd-configbucket-s3
bucket in the prd-appdev-oit-byu OIT AWS account for files named
<your net id>.yml in the format of example_config.yml in this repo.
The lambda takes around 5 seconds to set the slack status for each person who
has a yml file in the bucket so depending on how many yml files there are in the
bucket and where your yml file lands in the bucket ordering you can expect your
slack status to update 5 to n*5 seconds from when the lambda fires where n is
the number of yml files in the bucket. The lambda gives detailed logs of what it does
and any errors so look at the lambda's cloudwatch logs to debug any problems.
Feel free to run the lambda manually at any time.  It will just update everyone's
slack status with what is on their calendar.

## How to improve it
Please add any enhancement requests, issues, bugs, questions, etc as issues
on this github repo.  Pull requests are welcome.
Discussions around this are done in the #crazy-friday channel in slack.

## TODO
* (nate) Fix any issues filed on this repo
* Add a way to change the emoji based on the name of the event or the location of the event
