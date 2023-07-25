# Team Ticket App
## Slack -> Notion 

This is a simple Slack app to help field requests. I first made this when I was on a small data team (of two people) and we were fielding a high number of requests. I wanted to take advantage of the fact that everyone in the organization was already using Slack to make requests and this would be an easy tool to adopt. With this app, a slash command brings up a pop up form in Slack and the information entered into the form will become a ticket in Notion. The ticket is posted as a kanban card and automatically marked as unassigned. When the cards are assigned and moved through the different stages and into completion, a notification is posted in Slack to the ticket owner and to the team. Meta data from this process is stored in an S3 bucket.

The config file is set up to allow you to make small changes to text and labels in this project without updating the code. If you choose to makes these changes, you will need to update the config file to reflect the changes. Since new labels and text will impact the json payloads, you will need to run ...this test... to see the new json keys and update them in the  config file.

To setup the app you will need:
1. Notion account
2. Slack account & developer access 
3. Glitch account with a boosted service 
4. AWS S3 bucket 

## Set up steps:

- [ ] Remix (copy) the [Glitch project](https://glitch.com/edit/#!/fluorescent-occipital-objective)
- [ ] Set up your Slack App. Instructions below.
- [ ] Sign into Notion & copy this [template](https://jenmckaig.notion.site/jenmckaig/Data-Team-Tickets-976d4a8a3ec64449a3ee4f69d4e8bc1e)
- [ ] Create a [new Notion integration](https://developers.notion.com/docs/create-a-notion-integration) to get an API Token. Save the Database ID & the API Token. 
- [ ] Set up your AWS S3 bucket. The project requires two directories inside the bucket to house the metadata and logs. Those directories are currently named <b>data_tickets/</b> and <b>notifications/</b> and the names can be updated in the config file if you need to change them. You will need to have Write, Read, & List access to the bucket. Save the bucket name, directory names, aws access key, and aws secret key.
- [ ] Update your .env file in Glitch or wherever you are storing your env variables. You will need:
    - AWS_ACCESS_KEY_ID
    - AWS_SECRET_ACCESS_KEY
    - AWS_S3_BUCKET
    - SLACK_BOT_TOKEN
    - SLACK_APP_TOKEN
    - SLACK_SIGNING_SECRET
    - SLACK_CHANNEL_ID (Where you want notifications posted to the team.)
    - NOTION_DATABASE_ID
    - NOTION_TOKEN
    - [NOTION_PAGES_ENDPOINT](https://developers.notion.com/reference/post-page)
    - [NOTION_DB_ENDPOINT](https://developers.notion.com/reference/post-database-query)


### Setting up your app in Slack:

Documentation links
- [Slack Developer Docs](https://api.slack.com/docs)
- [Block Kit](https://api.slack.com/block-kit)
- [Slack SDK -> Python](https://slack.dev/python-slack-sdk/)
- [Slack Bolt -> Python](https://slack.dev/bolt-python/concepts)
- [Slash Commands](https://api.slack.com/interactivity/slash-commands)

Visit the Slack Developer Docs and go to <b>Your Apps</b> in the top right corner. Create a new app and select create from scratch.

On the <b>Basic Information Page</b> scroll down to the bottom and edit Display Information. Choose a name, color, and icon. You
can find free icons at [https://www.flaticon.com/].

Under the <b>Features Menu</b> on the left side of the screen go to the Slash Command page and enter your Slash command. The app 
default is <span style="color: red;"> /data-ticket </span> but you can use whatever you want, just be sure to update it in the config file.

Go to the <b>Oauth & Permissions Page</b> and scroll down to Bot Token scopes. Select the following:

- <span style="color: purple;">chat:write</span>
- <span style="color: purple;">chat:write.customize</span>
- <span style="color: purple;">chat:write.public</span>
- <span style="color: purple;">commands</span>
- <span style="color: purple;">im:write</span>
- <span style="color: purple;">users.profile:read</span>
- <span style="color: purple;">users:read</span>
- <span style="color: purple;">users:read.email</span>


Go to <b>App Home Page</b> and scroll down to the bottom. Turn on the Messages Tab and check on "Allow users to send
Slash commands and messages from the messages tab". 

Under the <b>Settings Menu</b> go the Socket Mode page and enable Socket Mode.  

Under the <b>Settings Menu</b> got to Install Your App and install. On the same page, copy your <u>Bot User OAuth Token</u> and save it somewhere for later.

On the <b>Basic Information Page</b> scroll to the bottom and generate your <u>App Level Token</u> with the scope <span style="color: purple;">connections:write</span>. Copy
and save it for later. On the same page copy your <u>Signing Secret</u> and save it for later.










