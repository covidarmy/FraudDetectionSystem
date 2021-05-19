import os
import threading
from dotenv import load_dotenv
import requests
from telegram.ext import Updater, ConversationHandler, CommandHandler, MessageHandler, Filters
from findNumbers import findNumbersInText
from pymongo import MongoClient
load_dotenv()
connectionURI = os.getenv("CONNECTION_URI")
client = MongoClient(connectionURI)
db = db = client.get_database('red-db')
col = db.Fraud


def startCommand(update, context):
    user = update.message.from_user
    startText = "Hey {} \U0001F44B \n\nI am a bot which could help you stay safe from fraudulents/suspicious covid leads. Here's a quick intro about me:\n\n1. To check for the credibility of a number, send /check\n2. To report a fraud number, send /report\n3. For more information, send /help\n\nYou can also visit https://covid.army for finding several resources.".format(
        user['first_name'])
    update.message.reply_text(
        startText, disable_web_page_preview=True)


def helpCommand(update, context):
    user = update.message.from_user
    helpText = "Hello {} \U0001F44B \n\nThis bot is an initiative by https://covid.army and it'll help you stay safe from 1k+ suspicious numbers in our constantly updating database. You can help us by reporting a fraud number which unfortunately, you've dealt with.\n\nSend /report to report a number.\n\nSend /check to check credibility of a number".format(
        user['first_name'])
    messageID = update.message.message_id
    update.message.reply_text(
        helpText, reply_to_message_id=messageID, disable_web_page_preview=True)


def reportCommand(update, context):
    update.message.reply_text(
        "Thank You for contributing \U0001F64F \nPlease enter the numbers you want to report. You can enter multiple numbers seperated by comma (,)")
    return reportThem


def checkCommand(update, context):
    update.message.reply_text(
        "Send the number you want to check. You can send multiple numbers seperated by comma (,)")
    return checkNumber


def reportThem(update, context):
    reportedNumbers = update.message.text
    jsonData = {"Numbers": reportedNumbers}

    def postReq():
        requests.post("https://verifynum.herokuapp.com/report", json=jsonData)
    thread = threading.Thread(target=postReq)
    thread.start()
    replyText = "Thank You \U00002728 \nThe numbers you've reported are under review \U0001F50D"
    update.message.reply_text(replyText)
    return ConversationHandler.END


def checkNumber(update, context):
    toCheck = update.message.text
    update.message.reply_text("Checking \U0000231B")
    response = requests.get(
        "https://verifynum.herokuapp.com/find/{}".format(toCheck)).json()
    replyText = "The entered numbers appear to be safe. Still we suggest to avoid any advance payments \U0001F64F"
    if response["Result"]:
        setOfFrauds = set(response["Values"])
        replyText = "The following numbers are found suspicious \U0001F6A8:\n\n"
        for i in setOfFrauds:
            replyText = replyText+i+"\n"

    update.message.reply_text(replyText)
    return ConversationHandler.END


def handleMessage(update, context):
    messageID = update.message.message_id
    update.message.reply_to_message
    text = str(update.message.text).lower()
    numbersInText = findNumbersInText(text)
    if(len(numbersInText) > 0):
        res = col.find({"phone_no": {"$in": numbersInText, "$exists": True}})
        allPresentNumbers = set([i['phone_no'] for i in res])
        if(len(allPresentNumbers) > 0):
            response = "\U0001F6A8 ALERT!! \U0001F6A8 \n\nThe following numbers are suspicious as per our database.\n"
            for i in allPresentNumbers:
                response = response+i+"\n"
            response += "\nFor finding leads and viewing disclaimer, visit: https://covid.army"
            update.message.reply_text(
                response, reply_to_message_id=messageID, disable_web_page_preview=True)


def error(update, context):
    update.message.reply_text("Oops! Didn't get that \U0001F440")


def main():
    print("Bot started")
    APIKey = os.getenv("API_KEY")
    updater = Updater(APIKey, use_context=True)
    dp = updater.dispatcher

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler(
            'report', reportCommand), CommandHandler('check', checkCommand)],
        fallbacks=[],

        states={
            reportThem: [MessageHandler(Filters.text, reportThem)],
            checkNumber: [MessageHandler(Filters.text, checkNumber)]
        },
    )

    dp.add_handler(conv_handler)
    dp.add_handler(CommandHandler("start", startCommand))
    dp.add_handler(CommandHandler("help", helpCommand))
    dp.add_handler(MessageHandler(Filters.text, handleMessage))
    dp.add_error_handler(error)

    updater.start_polling()
    updater.idle()


if __name__ == "__main__":
    main()
