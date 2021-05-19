# -*- coding: utf-8 -*-
"""
Created on Sun May  2 17:02:21 2021

@author: vishn
"""

from flask import Flask, json, jsonify, render_template, request
from pymongo import MongoClient
import re
import string
import emoji
import tweepy
from PIL import Image
import requests
import pytesseract
import io
import threading
from flask_cors import CORS
from datetime import datetime
from dotenv import load_dotenv
import os
load_dotenv()

app = Flask(__name__)
CORS(app)

# Re
exp = '(?!([0]?[1-9]|[1|2][0-9]|[3][0|1])[./-]([0]?[1-9]|[1][0-2])[./-]([0-9]{4}|[0-9]{2}))(\+?\d[\d -]{8,12}\d)'


def getNum(listRaw):
    if(len(listRaw) == 0):
        return listRaw
    listOfNumbers = []
    for tup in listRaw:
        for ele in tup:
            if ele != '':
                listOfNumbers.append(ele)
    curatedNumbers = []
    for number in listOfNumbers:
        number = "".join(e for e in number if e.isnumeric())
        # print("Number: ", number)
        if(len(number) > 10):
            curatedNumbers.append(number[-10:])
        else:
            curatedNumbers.append(number)
    return curatedNumbers


def getMeNum(listRaw):
    if(len(listRaw) == 0):
        return listRaw
    # listOfNumbers = list(filter(None, list(itertools.chain(*listRaw))))
    curatedNumbers = []
    for number in listRaw:
        number = "".join(e for e in number if e.isnumeric())
        # print("Number: ", number)
        if(len(number) > 10):
            curatedNumbers.append(number[-10:])
        else:
            curatedNumbers.append(number)
    return curatedNumbers


def cleanEmoji(text):
    # print(emoji.emoji_count(text))
    new_text = re.sub(emoji.get_emoji_regexp(), r"", text)
    return new_text


def cleanLinks(text):
    link_regex = re.compile(
        '((https?):((//)|(\\\\))+([\w\d:#@%/;$()~_?\+-=\\\.&](#!)?)*)', re.DOTALL)
    links = re.findall(link_regex, text)
    for link in links:
        text = text.replace(link[0], ', ')
    return text


def cleanText(text):
    entity_prefixes = ['@', '#']
    for separator in string.punctuation:
        if separator not in entity_prefixes:
            text = text.replace(separator, ' ')
    words = []
    for word in text.split():
        word = word.strip()
        if word:
            if word[0] not in entity_prefixes:
                words.append(word)
    return ' '.join(words)

# te=cleanText(cleanLinks(cleanEmoji("b\"RT @GuptaJay3762: #EmmanuelMacron  Turkey's President Tayyip Erdogan Calls For Boycott French Product But His Wife Poses With Hermes Paris")))
# print(list(set((getNum(re.findall(exp, te))+getNum(re.findall(exp, te.replace(" ","@")))))))


def findNumbersInText(tweetText):
    cleanedTweet = cleanText(cleanLinks(cleanEmoji(tweetText)))
    return list(set((getNum(re.findall(exp, cleanedTweet))+getNum(re.findall(exp, cleanedTweet.replace(" ", "@"))))))


def findNumbersInImage(arrayOfUrls):
    allNumbersInThisImage = []
    for imageObj in arrayOfUrls:
        responseImg = requests.get(imageObj['media_url_https'])
        imgPresent = Image.open(
            io.BytesIO(responseImg.content))
        textOnImage = pytesseract.image_to_string(imgPresent)
        cleanedTextOnImage = cleanText(
            cleanLinks(cleanEmoji(textOnImage)))
        allNumbersInThisImage += list(set((getNum(re.findall(exp, cleanedTextOnImage))+getNum(
            re.findall(exp, cleanedTextOnImage.replace(" ", "@"))))))
    return allNumbersInThisImage


def findFraudInThisTweet(tweet, latestFetchedId):
    allFraudNumbers = []
    phoneNumbersFromImage = []
    phoneNumbersFromText = []
    tweetJson = tweet._json
    if not tweet.retweeted and 'RT' not in tweet.full_text[:5]:
        latestFetchedId = max(latestFetchedId, tweet.id_str)
        tweetText = tweet.full_text

        phoneNumbersFromText += findNumbersInText(tweetText)
        if(len(phoneNumbersFromText) == 0):
            if("extended_entities" in tweetJson.keys()):
                # Check For OCR
                phoneNumbersFromImage = findNumbersInImage(
                    tweetJson['extended_entities']['media'])
    allFraudNumbers = phoneNumbersFromText+phoneNumbersFromImage
    return allFraudNumbers, latestFetchedId


def findFrauds(resource, since, api):
    allFraudNumbers = []
    latestFetchedId = ""
    for tweet in tweepy.Cursor(api.search, q="{} (fraud OR scam)".format(resource), lang="en", result_type='recent', tweet_mode='extended', since_id=since).items():
        # print("\n\nIn For!!")
        fraudNumbersInThisTweet, latestFetchedId = findFraudInThisTweet(
            tweet, latestFetchedId)
        allFraudNumbers += fraudNumbersInThisTweet
    return allFraudNumbers, latestFetchedId


def createMongoConnection():
    # MongoDB
    client = MongoClient(os.getenv("MONGO_URI_FRAUD"))
    db = client.get_database('Suspicious_Listings')
    col = db.Listings
    return client, col


def createMongoConnectionCovidArmy():
    client = MongoClient(os.getenv("MONGO_URI_COVID_ARMY"))
    return client


@app.route('/', methods=['GET'])
def homePage():
    return render_template("index.html")


@app.route('/find/<numberArray>', methods=['GET'])
def search(numberArray):
    numArray = numberArray.split(',')
    cleanedNumbers = getMeNum(numArray)
    # MongoDB
    client = createMongoConnectionCovidArmy()
    db = db = client.get_database('red-db')
    col = db.Fraud
    res = col.find({"phone_no": {"$in": cleanedNumbers, "$exists": True}})
    client.close()  # Close Connection!
    allPresentNumbers = list(set([i['phone_no'] for i in res]))
    if len(allPresentNumbers) == 0:
        return jsonify(
            Result=False,
            Status=404
        )
    else:
        return jsonify(
            Result=True,
            Status=200,
            Values=allPresentNumbers
        )


@app.route('/updateDatabase', methods=['GET'])
def updateDatabase():
    # Twitter
    consumer_key = os.getenv("consumer_key")
    consumer_key_secret = os.getenv("consumer_key_secret")
    access_token = os.getenv("access_token")
    access_token_secret = os.getenv("access_token_secret")
    auth = tweepy.OAuthHandler(consumer_key, consumer_key_secret)
    auth.set_access_token(access_token, access_token_secret)
    api = tweepy.API(auth, wait_on_rate_limit=True)

    client, col = createMongoConnection()

    colJson = col.find_one({'contentType': 'sinceIds'})
    sinceIds = {
        'Oxygen': colJson['Oxygen'],
        'Remdesivir': colJson['Remdesivir'],
        'Favipiravir': colJson['Favipiravir'],
        'Ventilator': colJson['Ventilator'],
        'Plasma': colJson['Plasma'],
        'Tocilizumab': colJson['Tocilizumab'],
        'ICU': colJson['ICU'],
        'Beds': colJson['Beds']
    }
    updatedSinceIds = dict()

    def threadThis():
        fraudAcrossAllResources = []
        # print("Starting the thread!!")
        # Iterate over and send each resource to capture its frauds
        clientCovid = createMongoConnectionCovidArmy()
        dbCovid = clientCovid.get_database("red-db")
        colCovid = dbCovid.Fraud
        dbCovid2 = clientCovid.get_database("staging-db")
        colCovid2 = dbCovid2.Fraud
        for resource, sinceID in sinceIds.items():
            # print("\nCurrently Working On: {} Resource\n".format(resource))
            allFraudNumbers, updatedId = findFrauds(
                resource.lower(), sinceID, api)
            fraudAcrossAllResources += allFraudNumbers
            # Update the ID
            # print("Completed Working\nAll Frauds: {}\n".format(allFraudNumbers))

            updatedSinceIds[resource] = updatedId
            # print("\nUpdated Since IDs: {}\n".format(updatedSinceIds))
            createRecord = {
                'Numbers': allFraudNumbers
            }
            updateQuery = {"$addToSet": {
                "Numbers": {"$each": createRecord['Numbers']}}}
            col.update_one({"Resource": resource}, updateQuery)
            # print("Updated Resource: {}".format(resource))

        for res, tim in sinceIds.items():
            updatedSinceIds[res] = max(updatedSinceIds[res], tim)

        col.update({"contentType": "sinceIds"}, {
            "$set": updatedSinceIds}, upsert=True)

        client.close()

        # Update Covid.Army Db

        createRecordCovid = [{
            'phone_no': i,
            "Date": str(datetime.now())
        } for i in fraudAcrossAllResources]

        for i in createRecordCovid:
            colCovid.update(i, i, upsert=True)
            colCovid2.update(i, i, upsert=True)
        clientCovid.close()
        # print("Thread ended!")

    thread = threading.Thread(target=threadThis)
    thread.start()
    return jsonify(
        Status=200
    )


@app.route('/report', methods=['POST'])
def report():
    data = request.get_json()
    numberArray = data['Numbers']
    numArray = numberArray.split(',')
    cleanedNumbers = getMeNum(numArray)
    clientCovid = createMongoConnectionCovidArmy()
    dbCovid = clientCovid.get_database("red-db")
    colCovid = dbCovid.Fraud
    dbCovid2 = clientCovid.get_database("staging-db")
    colCovid2 = dbCovid2.Fraud

    addToStash = {
        "StashNumbers": cleanedNumbers
    }

    addToStashQuery = {"$push": {
        "Stash": {"$each": addToStash['StashNumbers']}
    }}

    colCovid.update_one({"Title": "Fraud"}, addToStashQuery)

    # clientCovid.close()

    stashArrayCursor = colCovid.find({"Title": "Fraud"})
    stashArray = stashArrayCursor[0]['Stash']
    confirmedFrauds = []
    for number in cleanedNumbers:
        if(stashArray.count(number) > 1):
            confirmedFrauds.append(number)

        # Create Update Query!
    createRecordCovid = {
        'Numbers': confirmedFrauds
    }
    updateQueryCovid = {"$addToSet": {
        "Numbers": {"$each": createRecordCovid['Numbers']}}}

    # Write to Covid.Army

    createRecCovidArmy = [{
        "phone_no": i,
        "Date": str(datetime.now())
    } for i in confirmedFrauds]

    for i in createRecCovidArmy:
        colCovid.update(i, i, upsert=True)
        colCovid2.update(i, i, upsert=True)

        # Write to Fraud Detector
    client, col = createMongoConnection()
    col.update_one({"Resource": "Unspecified"}, updateQueryCovid)
    client.close()
    clientCovid.close()
    return jsonify(
        Status=200
    )


@app.route("/getAllFrauds", methods=['GET'])
def getAllFrauds():
    client, col = createMongoConnection()
    res = col.find()
    jsonArray = res[1:]

    createResp = [{"Resource": i['Resource'],
                   "Numbers": i['Numbers']} for i in jsonArray]
    client.close()
    return jsonify(
        Status=200,
        Frauds=createResp
    )
