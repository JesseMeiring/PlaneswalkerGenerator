import sys
from math import *
import mtgtools
from mtgtools.MtgDB import MtgDB
from mtgtools.PCard import PCard
from mtgtools.PCardList import PCardList
from mtgtools.PSet import PSet
from mtgtools.PSetList import PSetList
import ZODB
import pickle
import random
import time
from PIL import Image, ImageFont, ImageDraw
import requests
import os
from datetime import datetime
from svglib.svglib import svg2rlg
from reportlab.graphics import renderPM

bigTextBoxTop = 580
textBoxTop = 665
textBoxBottom = 946
textBoxLeft = 39
textBoxRight = 682
loyaltyTop = 923
loyaltyBottom = 990
loyaltyLeft = 600
loyaltyRight = 700
mCostFirstSymbolLeft = 650
mCostTop = 48
mCostSymbolSize = 36
mCostSymbolSpacing = 38

def PWAlreadyPresent(card: PCard, arrCard):
	for PWCard in arrCard:
		if(card.name == PWCard.name):
			return True
	return False

def latestReleaseOfCard(card: PCard, allCards: PCardList, sets: PSetList) -> bool:
	#allVersions = allCards.where(name=card.name)
	setsAppearing = sets.filtered(lambda pset: any(pset.where_exactly(name=card.name)))
	oldestSetDate = datetime.strptime(setsAppearing[0].released_at,'%Y-%m-%d')
	oldestSetName = setsAppearing[0].name
	card.reprint
	s: PSet
	for s in setsAppearing:
		if(datetime.strptime(s.released_at,'%Y-%m-%d') < oldestSetDate):
			oldestSetDate = datetime.strptime(s.released_at,'%Y-%m-%d')
			oldestSetName = s.name
	return oldestSetName == card.set_name

def legitimatePW(card: PCard) -> bool:
	legit:bool = True
	cardSet = scryfall_sets.where_exactly(name=card.set_name)
	legit = legit and cardSet[0].set_type != 'funny'
	legit = legit and cardSet[0].set_type != 'token'
	legit = legit and cardSet[0].set_type != 'promo'
	legit = legit and not "//" in card.name
	legit = legit and card.legalities['vintage'] == 'legal'
	legit = legit and card.promo_types == None
	return legit

def spitDatShitOut(setOfCards):
	print(len(setOfCards))
	card:PCard = None
	for card in setOfCards:
		print(card.name)
		print(card.set)
		print(card.oracle_text)

class PWBrokenDown:
	def __init__(self, name="", oracle_text="", cmc=0, manaCost="{0}", loyalty:int=0, oracle_id:str = ""):
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
		self.oracle_id = oracle_id
		self.image: Image.Image = None

	def processAbilities(self):
		abilityLines = self.oracle_text.split("\n")
		passivesLines = []
		for line in abilityLines:
			temp = line.split(":", 1)
			if(len(temp) == 2 and len(temp[0]) < 4):
				tempAbil = Ability(temp[0],temp[1], abilityLines.index(line), self)
				if(tempAbil.costInt * -1 > self.loyalty): 
					tempAbil.ult = True
				self.abilities.append(tempAbil)
			else:
				passivesLines.append(line)
		if(len(passivesLines) > 0):
			tempAbil = Ability('Passive',"\n".join(passivesLines), 0, self)
			self.abilities.insert(0, tempAbil)
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
		aSources = []
		for a in self.abilities:
			aSources.append(a.originPW.name)
		print("ability sources: " + "; ".join(aSources))
		print("loyalty: " + str(self.loyalty))
		print("")

class Ability:
	def __init__(self, costText:str = "0", ability_text: str = "None", sourceIndex: int =-1, originPW=None):
		self.costText = costText
		self.ability_text = ability_text
		self.ult = False
		self.sustainablePWSource = True
		self.costInt = self.costToInt()
		self.sourceIndex = sourceIndex
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

def NameCombinator(PW1: PWBrokenDown,PW2: PWBrokenDown,PW3: PWBrokenDown) -> str:
	nameArr = []
	nameArr.append(PW1.name.split(" ")[0])
	nameArr.append(PW2.name.split(" ")[1])
	component3list = PW3.name.split(" ")
	c3end = component3list[2:]
	nameArr.append(" ".join(c3end))
	return " ".join(nameArr)

def cerberusPW(ThreePWCards):
	PW1: PWBrokenDown = PWBrokenDown()
	PW2: PWBrokenDown = PWBrokenDown()
	PW3: PWBrokenDown = PWBrokenDown()
	A1: Ability = Ability()
	A2: Ability = Ability()
	A3: Ability = Ability()
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
	loyalty: int = int(round((PW1.loyalty + PW2.loyalty + PW3.loyalty) / 3, 0))
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
	CPWName = NameCombinator(PW1, PW2, PW3)
	CPW = PWBrokenDown(CPWName,o_text,cmc,cost,loyalty)
	AbilArr = [A1, A2, A3] 
	for A in AbilArr:
		if A.costText == "Passive":
			CPW.abilities.append(A)
			AbilArr.remove(A)
	AbilArr.sort(key = lambda a: a.costInt, reverse=True)
	CPW.abilities.extend(AbilArr)
	AbilArr.clear()
	baseImage = getCardImage(PW1, 'full')
	for CAbil in CPW.abilities:
		abilityImage = getCardImage(CAbil.originPW, "A" + str(CAbil.sourceIndex + 1))
		insertAbilityOnImage(baseImage, abilityImage, [A1, A2, A3].index(CAbil))
	addCardName(baseImage, CPWName)
	addManaCostOnImage(baseImage, cost)
	addStartingLoyalty(baseImage, loyalty)
	#baseImage.show()
	CPW.image = baseImage
	return CPW

def addCardName(baseImage: Image.Image, name: str):
	TitleCorner = [64, 48]
	fontDir = str(os.getcwd())+'\\Goudy Mediaeval DemiBold.ttf'
	title_font = ImageFont.truetype(fontDir, 40)
	drawnImage: ImageDraw.ImageDraw = ImageDraw.Draw(baseImage)
	titleSpace = drawnImage.textsize(name, title_font)
	#px = baseImage.load()
	titleBGColor = baseImage.getpixel((130, 44))
	drawnImage.rectangle(
		xy=[
		TitleCorner[0] - 2,
		TitleCorner[1],
		680, #TitleCorner[0] + titleSpace[0] + 2,
		TitleCorner[1] + titleSpace[1] - 2
		], 
		fill=titleBGColor
	)
	drawnImage.text(TitleCorner, name, (0, 0, 0), font=title_font)

def addStartingLoyalty(baseImage: Image.Image, loyalty: int):
	symbolFolder = str(os.getcwd())+"\\symbol_images\\"
	loyaltySymbolPath: str = symbolFolder + str(loyalty) + "_Loyalty.png"
	if os.path.exists(loyaltySymbolPath):
		lSym = Image.open(loyaltySymbolPath)
		baseImage.paste(lSym, [loyaltyLeft, loyaltyTop])

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
	if not os.path.exists(path):
		os.makedirs(path)
	for c in cards:
		img_path = path + c.id + ".png"
		if not os.path.exists(img_path):
				print("Saving " + c.image_uris['png'] + " at this path " + img_path)
				r = requests.get(c.image_uris['png'])
				with open(img_path,'wb') as f:
					f.write(r.content)
				time.sleep(.5)

def downloadSymbolImages(path):
	if not os.path.exists(path):
		os.makedirs(path)
	symbolList = requests.get("https://api.scryfall.com/symbology").json()
	for s in symbolList['data']:
		sym: str = s['symbol']
		sym = sym[1:-1].replace('/','_')
		img_path = path + sym + ".png"
		svg_path = path + sym + ".svg"
		if not os.path.exists(img_path):
				print("Saving " + s['svg_uri'] + " at this path " + svg_path)
				r = requests.get(s['svg_uri'])
				with open(svg_path,'wb') as f:
					f.write(r.content)
				time.sleep(.1)
				symbolDrawing = svg2rlg(svg_path)
				renderPM.drawToFile(symbolDrawing, img_path, fmt='PNG')

def pullLoyaltySymbols(cards: list[PWBrokenDown], path: str):
	if not os.path.exists(path):
		os.makedirs(path)
	for c in cards:
		loyaltySymbolPath: str = path + str(c.loyalty) + "_Loyalty.png"
		if not os.path.exists(loyaltySymbolPath):
			getCardImage(c, 'loyalty').save(loyaltySymbolPath)
				
def getCardImage(card: PWBrokenDown, part: str = 'full') -> Image.Image:
	im1: Image.Image = Image.open(imageFolder + card.oracle_id + ".png")
	box: tuple[int, int, int, int] = (0, 0, im1.width, im1.height)
	# AProportion = 1 / len(card.abilities)
	# AHeight = (textBoxBottom - textBoxTop) * AProportion
	match part:
		case "full":
			box = (0, 0, im1.width, im1.height)
		case "A1":
			box = abilityImageLocation(len(card.abilities), 0)
		case "A2":
			box = abilityImageLocation(len(card.abilities), 1)
		case "A3":
			box = abilityImageLocation(len(card.abilities), 2)
		case "A4":
			box = abilityImageLocation(len(card.abilities), 3)
		case "loyalty":
			box = (
				loyaltyLeft,
				loyaltyTop,
				loyaltyRight,
				loyaltyBottom
			)
	return im1.crop(box)

def addManaCostOnImage(baseImage: Image.Image, symbolString: str) -> Image.Image:
	symbolFolder = str(os.getcwd())+"\\symbol_images\\"
	symbolArr = symbolString[1:-1].split("}{")
	symbolLeft = mCostFirstSymbolLeft - (mCostSymbolSpacing * (len(symbolArr) - 1))
	for s in symbolArr:
		sImage: Image.Image = Image.open(symbolFolder + s + ".png")
		sImage = sImage.resize([mCostSymbolSize, mCostSymbolSize])
		baseImage.paste(sImage, [symbolLeft, mCostTop])
		symbolLeft += mCostSymbolSpacing

def insertAbilityOnImage(baseImage: Image.Image, AbilityImage: Image.Image, AIndex: int) -> Image.Image:
	Location = abilityImageLocation(3, AIndex)
	Size = [Location[2] - Location[0], Location[3] - Location[1]]
	AbilityImage = AbilityImage.resize(Size)
	baseImage.paste(AbilityImage, abilityImageLocation(3, AIndex)[0:2])

def abilityImageLocation(AbilityCount: int, AbilIndex: int = 0) -> tuple[int, int, int, int]:
	AProportion = 1 / AbilityCount
	boxTop = textBoxTop
	if(AbilityCount > 3):
		boxTop = bigTextBoxTop
	AHeight = (textBoxBottom - boxTop) * AProportion
	box = (
		textBoxLeft, 
		floor(boxTop + (AbilIndex * AHeight)), 
		textBoxRight,
		floor(boxTop + ((AbilIndex + 1) * AHeight))
	)
	return box

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

	c: PCard
	for c in planeswalker_cards:
		#if(planeswalker_cards[x].name != planeswalker_cards[x-1].name):
		#if(latestReleaseOfCard(planeswalker_cards[x], planeswalker_cards, scryfall_sets)):
		if(not c.reprint):
			if (legitimatePW(c)):
				if(not PWAlreadyPresent(c,pw_sorted)):
					pw_sorted.append(c)
	printStatus("Filter repeats, joke sets and split cards")
	
	filehandler = open('Planeswalkers_Card_Objects', 'wb')
	pickle.dump(pw_sorted,filehandler)
	filehandler.close
	printStatus("Saved Interpreted PW Objects as Planeswalkers_Card_Objects")

	pw_parsed = []
	card: PCard
	for card in pw_sorted:
		temp = PWBrokenDown(card.name, card.oracle_text, card.cmc, card.mana_cost, card.loyalty, card.id)
		pw_parsed.append(temp)
	printStatus("Build PW interpreted objects")
	
	filehandler = open('Planeswalkers_Parsed', 'wb')
	pickle.dump(pw_parsed,filehandler)
	filehandler.close
	printStatus("Saved Interpreted PW Objects as Planeswalkers_Parsed")
else:
	filereader = open('Planeswalkers_Card_Objects', 'rb')
	pw_sorted = pickle.load(filereader)
	filereader = open('Planeswalkers_Parsed', 'rb')
	pw_parsed = pickle.load(filereader)
	printStatus("Imported Planeswalker Data from saved data")

imageFolder = str(os.getcwd())+"\\card_images\\"
downloadMissingCardImages(pw_sorted, imageFolder)
symbolFolder = str(os.getcwd())+"\\symbol_images\\"
downloadSymbolImages(symbolFolder)
pullLoyaltySymbols(pw_parsed, symbolFolder)

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
genImageFolder = str(os.getcwd())+"\\generated_card_images\\"
for i in range(100):
	rPW1 = random.choice(pw_parsed)
	rPW2 = random.choice(pw_parsed)
	rPW3 = random.choice(pw_parsed)
	newPW = cerberusPW([rPW1, rPW2, rPW3])
	print("Random PW #" + str(i))
	newPW.printDetails()
	newPW.image.save(genImageFolder + 'Planeswalker_' + str(i) + '.png')
printStatus("Generate some random PWs")

rPW = random.choice(pw_parsed)
#getCardImage(rPW, "Loyalty").show()
