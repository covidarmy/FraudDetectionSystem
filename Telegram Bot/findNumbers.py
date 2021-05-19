import re


# Re
exp = '(?!([0]?[1-9]|[1|2][0-9]|[3][0|1])[./-]([0]?[1-9]|[1][0-2])[./-]([0-9]{4}|[0-9]{2}))(\+?\d[\d -]{8,12}\d)'


def getNum(listRaw):
    if(len(listRaw) == 0):
        return listRaw
    #print("Raw: ", listRaw)
    listOfNumbers = []
    for tup in listRaw:
        for ele in tup:
            if ele != '':
                listOfNumbers.append(ele)
    #print("List of numbers: ", listOfNumbers)
    curatedNumbers = []
    for number in listOfNumbers:
        number = "".join(e for e in number if e.isalnum())
        #print("Number: ", number)
        if(len(number) > 10):
            curatedNumbers.append(number[-10:])
        else:
            curatedNumbers.append(number)
    return curatedNumbers


def findNumbersInText(tweetText):
    return list(set((getNum(re.findall(exp, tweetText)))))
