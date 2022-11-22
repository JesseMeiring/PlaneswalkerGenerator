import sys
from math import *
import mtgtools
from mtgtools.MtgDB import MtgDB
import ZODB
import pickle
import random
import time
import PIL
import urllib.request
import os

def fromJokeSet(card):
	cardSet = scryfall_sets.where(code=card.set)
	return cardSet[0].set_type == 'funny' or cardSet[0].set_type == 'token'

def spitDatShitOut(setOfCards):
	print(len(setOfCards))
	for card in setOfCards:
		print(card.name)
		print(card.set)
		print(card.oracle_text)

class PWBrokenDown:
	def __init__(self, name="", oracle_text="", cmc=0, manaCost="{0}", loyalty=0):
		self.name = name
		self.oracle_text = oracle_text
		self.abilities = []
		self.cmc = cmc
		self.manaCost = manaCost
		self.colorWeight = self.popColorWeights()
		if(loyalty == "X"):
			self.loyalty = 0
		else:
			self.loyalty = int(loyalty)

	def processAbilities(self):
		abilityLines = self.oracle_text.split("\n")
		passivesLines = []
		for line in abilityLines:
			temp = line.split(":", 1)
			if(len(temp) == 2 and len(temp[0]) < 4):
				tempAbil = Ability(temp[0],temp[1], self)
				if(tempAbil.costInt * -1 > self.loyalty): 
					tempAbil.ult = True
				self.abilities.append(tempAbil)
			else:
				passivesLines.append(line)
		if(len(passivesLines) > 0):
			tempAbil = Ability('Passive',"\n".join(passivesLines), self)
			self.abilities.append(tempAbil)
		if(not self.sustainablePW()):
			for a in self.abilities:
				a.sustainablePWSource = False

	def popColorWeights(self):
		colors = ['W','U','B','R','G']
		colorWeightsArr = []
		for color in colors:
			colorWeightsArr.append(len(self.manaCost.split(color)) - 1)
		return colorWeightsArr

	def sustainablePW(self):
		for a in self.abilities:
			if("+" in a.costText):
				return True
		return False

	def pullLoyaltyAbility(self, type = "any"):
		plusAbilities = []
		for a in self.abilities:
			if((type == "plus" and "+" in a.costText) or (type == "ult" and a.ult) or (type == "any")):
				plusAbilities.append(a)
		if(len(plusAbilities) > 0):
			return random.choice(plusAbilities)
		return None

	def printDetails(self):
		print("Name: " + self.name)
		print("manaCost: " + self.manaCost)
		print("oracle_text: " + self.oracle_text)
		aStr = "ability sources: "
		aSources = []
		for a in self.abilities:
			aSources.append(a.originPW.name)
		print("ability sources: " + "; ".join(aSources))
		print("loyalty: " + str(self.loyalty))
		print("")

class Ability:
	def __init__(self, costText="0", ability_text="None", originPW=None):
		self.costText = costText
		self.ability_text = ability_text
		self.ult = False
		self.sustainablePWSource = True
		self.costInt = self.costToInt()
		self.originPW = originPW

	def costToInt(self):
		str = self.costText
		if("Passive" in str or "X" in str):
			return 0
		if("+" in str):
			str.replace("+","")
		if("−" in str):
			return -int(str.replace("−",""))
		return int(str)

def cerberusPW(ThreePWCards):
	PW1 = PWBrokenDown()
	PW2 = PWBrokenDown()
	PW3 = PWBrokenDown()
	A1 = Ability()
	A2 = Ability()
	A3 = Ability()
	posPW = []
	ultPW = []
	for p in ThreePWCards:
		if(p.pullLoyaltyAbility("plus") != None):
			posPW.append(p)
		if(p.pullLoyaltyAbility("ult") != None):
			ultPW.append(p)
	susDesignViable = (len(posPW) > 1 and len(ultPW) > 0) or (len(posPW) > 2 and len(ultPW) > 1)
	if(susDesignViable):
		if len(posPW) > len(ultPW):
			PW3 = random.choice(ultPW)
			ThreePWCards.remove(PW3)
			if PW3 in posPW:
				posPW.remove(PW3)
			PW1 = random.choice(posPW)
			ThreePWCards.remove(PW1)
			PW2 = random.choice(ThreePWCards)
		else:
			PW1 = random.choice(posPW)
			ThreePWCards.remove(PW1)
			if PW1 in ultPW:
				ultPW.remove(PW1)
			PW3 = random.choice(ultPW)
			ThreePWCards.remove(PW3)
			PW2 = random.choice(ThreePWCards)
		A1 = PW1.pullLoyaltyAbility("plus")
		A2 = PW2.pullLoyaltyAbility("any")
		A3 = PW3.pullLoyaltyAbility("ult")
	else:
		PW1 = ThreePWCards[0]
		PW2 = ThreePWCards[1]
		PW3 = ThreePWCards[2]
		A1 = PW1.pullLoyaltyAbility("any")
		A2 = PW2.pullLoyaltyAbility("any")
		A3 = PW3.pullLoyaltyAbility("any")

	A1_text = A1.costText + ":" + A1.ability_text
	A2_text = A2.costText + ":" + A2.ability_text
	A3_text = A3.costText + ":" + A3.ability_text

	o_text = "\n".join([A1_text, A2_text, A3_text])

	cmc = round((PW1.cmc + PW2.cmc + PW3.cmc) / 3, 0)
	loyalty = round((PW1.loyalty + PW2.loyalty + PW3.loyalty) / 3, 0)
	colorWeight = []
	for c in range(len(PW1.colorWeight)):
		colorWeight.append(ceil((PW1.colorWeight[c] + PW2.colorWeight[c] + PW3.colorWeight[c])/3))

	remainingCost = cmc
	cost = ""
	syms = ['{W}','{U}','{B}','{R}','{G}']
	for sym in range(5):
		if(colorWeight[sym]>0):
			cost += syms[sym]*colorWeight[sym]
			remainingCost -= colorWeight[sym]
	if(remainingCost > 0):
		cost = "{" + str(int(remainingCost)) + "}" + cost
	CPW = PWBrokenDown("Cerberus",o_text,cmc,cost,loyalty)
	CPW.abilities = [A1, A2, A3]
	return CPW

def printStatus(msg=None):
	print("")
	TotalTime = time.time() - startTime
	try: splitTime
	except NameError: splitTime = 0
	splitTime = TotalTime - splitTime
	if(msg == None):
		print("TotalTime: " + str(TotalTime) + "; SplitTime: " + str(splitTime))
	else:
		print(msg + "; TotalTime: " + str(TotalTime) + "; SplitTime: " + str(splitTime))
	print("")

def downloadMissingCardImages(cards, path):
	for c in cards:
		img_path = c.id + ".png"
		if not os.path.exists(img_path):
				print("Saving " + c.image_uris['png'] + " at this path " + img_path)
				#urllib.request.urlretrieve(c.image_uris['png'], img_path)

startTime = time.time()
splitTime = 0
useSavedData = True
if(not useSavedData):
	mtg_db = MtgDB("my_db.fs")
	scryfall_cards = mtg_db.root.scryfall_cards
	scryfall_sets = mtg_db.root.scryfall_sets
	printStatus("Initialize MTG Database")

	planeswalker_cards = scryfall_cards.where(type_line="Planeswalker")
	planeswalker_cards = planeswalker_cards.sorted(lambda card: card.name)
	pw_sorted = []
	printStatus("Search for Planeswalker cards")

	for x in range(len(planeswalker_cards)):
		if(planeswalker_cards[x].name != planeswalker_cards[x-1].name):
			if not(fromJokeSet(planeswalker_cards[x])):
				if not "//" in planeswalker_cards[x].name:
					if planeswalker_cards[x].legalities['vintage'] != 'not_legal':
						pw_sorted.append(planeswalker_cards[x])
	printStatus("Filter repeats, joke sets and split cards")
	
	filehandler = open('Planeswalkers_Card_Objects', 'wb')
	pickle.dump(pw_sorted,filehandler)
	filehandler.close
	printStatus("Saved Interpreted PW Objects as Planeswalkers_Card_Objects")

	pw_parsed = []
	for card in pw_sorted:
		temp = PWBrokenDown(card.name, card.oracle_text, card.cmc, card.mana_cost, card.loyalty)
		pw_parsed.append(temp)
	printStatus("Build PW interpreted objects")
	
	filehandler = open('Planeswalkers_Parsed', 'wb')
	pickle.dump(pw_parsed,filehandler)
	filehandler.close
	printStatus("Saved Interpreted PW Objects as Planeswalkers_Parsed")
else:
	filereader = open('Planeswalkers_Card_Objects', 'rb')
	planeswalker_cards = pickle.load(filereader)
	filereader = open('Planeswalkers_Parsed', 'rb')
	pw_parsed = pickle.load(filereader)
	printStatus("Imported Planeswalker Data from saved data")

imageFolder = str(os.getcwd())+"\\card_images\\"
downloadMissingCardImages(planeswalker_cards, imageFolder)

#for each plansewalker, take thier abilities and break them into Ability objects
#Also, classifies them as ult (more loyalty cost than the starting loyalty
#and labels all abilities that come from planeswalkers unable to gain loyalty

all_abilities = []
for pw in pw_parsed:
	pw.processAbilities()
	for abl in pw.abilities:
		all_abilities.append(abl)
printStatus("Convert Oracle text to ability objects")

print("---Planeswalkers---")
for i in range(5):
	rPW1 = random.choice(pw_parsed)
	rPW2 = random.choice(pw_parsed)
	rPW3 = random.choice(pw_parsed)
	newPW = cerberusPW([rPW1, rPW2, rPW3])
	print("Random PW #" + str(i))
	newPW.printDetails()
printStatus("Generate some random PWs")
print(os.getcwd())