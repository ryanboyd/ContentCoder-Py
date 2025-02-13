#!/usr/bin/env python
# encoding: utf-8
# python 3.9.2
# content_coder_py
# updated on: 2023-02-01
# by Ryan L. Boyd, Ph.D.
# ryan@ryanboyd.io

import csv
import re
import os
import io
import json

from itertools import zip_longest
from .create_export_dir import create_export_dir


containsWildcardRegex = re.compile(r'(?<!\\\\)\*')
literalAsteriskRegex = re.compile(r'\\\\\\\*')

class ContentCodingDictionary:

    def __init__(self, dicFilename, fileEncoding, fromString=False, dictString=None,
                 dictFormat=None, abbreviations=None, verbose=True):

        self.abbreviationDict = abbreviations

        self.wildcardMemory = {}
        self.maxWords = -1
        self.numCats = -1
        self.numberOfWildcards = 0

        self.catNames = []
        self.catOrder = {}
        self.catNamesHierarchical = {}

        self.dictTermCatMap = {}
        self.dictDataStandard = {}
        self.dictDataWildsList = {}
        self.dictDataWildsRegEx = {}

        # what to do if we're loading a dictionary from a string
        if fromString:
            if dictFormat == '2007':
                self.LoadDictionary2007(dicText=dictString, verbose=verbose)
            elif dictFormat == '2022':
                self.LoadDictionary2022(dicText=dictString, verbose=verbose)

        # what to do if we're doing it from a file
        else:

            dictStringRead = self.ReadDictFile(dicFilename=dicFilename, fileEncoding=fileEncoding)

            if dicFilename.endswith('dicx') or dicFilename.endswith('csv'):
                self.LoadDictionary2022(dicText=dictStringRead, verbose=verbose)
            elif dicFilename.endswith('dic'):
                self.LoadDictionary2007(dicText=dictStringRead, verbose=verbose)
            else:
                print('This dictionary file needs to have one of the appropriate extensions (dic, dicx, csv).')

        for numberOfWords in range(self.maxWords, 0, -1):
            self.wildcardMemory[numberOfWords] = {}

        return

    def ReadDictFile(self, dicFilename, fileEncoding):
        dicText = None
        with open(dicFilename, 'r', encoding=fileEncoding) as fin:
            dicText = fin.read()

        return dicText

    def FixAbbreviations(self, dicTerm):

        if dicTerm in self.abbreviationDict.keys():
            return self.abbreviationDict[dicTerm]
        else:
            return dicTerm

    def LoadDictionary2007(self, dicText, verbose=True):
        """Loads up a dictionary that is in the 2007/2015 format."""

        # this one is specific to the 2007-style dictionaries
        catNameNumberMap = {}

        dicSplit = dicText.split('%', 2)
        dicHeader = dicSplit[1]
        dicBody = dicSplit[2]

        # this sets up all of the header information for our dictionary
        orderCounts = 0
        for line in dicHeader.splitlines():
            if line.strip() == '':
                continue

            lineSplit = line.strip().split('\t')
            self.catOrder[lineSplit[1]] = orderCounts
            orderCounts += 1

            self.catNames.append(lineSplit[1])
            self.catNamesHierarchical[lineSplit[1]] = lineSplit[1]

            catNameNumberMap[lineSplit[0]] = lineSplit[1]

        self.numCats = len(self.catNames)

        # iterate over all of the rows of the dictionary
        for line in dicBody.splitlines():

            lineSplit = line.strip().split('\t')

            dicTerm = self.FixAbbreviations(dicTerm=' '.join(lineSplit[0].lower().strip().split()))

            if dicTerm.strip() == '':
                continue

            dicCategories = {}

            # build the list of categories that we're going to map this word to
            for i in range(1, len(lineSplit)):
                entryCatMarker = lineSplit[i].strip()
                # skip empty entry
                if entryCatMarker == '':
                    continue
                else:
                    dicCategories[catNameNumberMap[entryCatMarker]] = 1.0

            self.UpdateCategories(dicTerm=dicTerm, newCategories=dicCategories, verbose=False)

        if verbose:
            print('Dictionary loaded.')
        return

    def LoadDictionary2022(self, dicText, verbose=True):
        """Loads up a dictionary that is in the LIWC-22 format."""

        csvr = csv.reader(dicText.splitlines(), quotechar='"', delimiter=',')

        # set up the category names
        header = csvr.__next__()

        if len(header) > 1:

            self.catNames = header[1:]
            self.numCats = len(self.catNames)
            for i in range(0, self.numCats):
                self.catOrder[self.catNames[i]] = i
                self.catNamesHierarchical[self.catNames[i]] = self.catNames[i]

        # iterate over all of the rows of the dictionary
        for line in csvr:

            dicTerm = self.FixAbbreviations(dicTerm=' '.join(line[0].lower().strip().split()))

            if dicTerm.strip() == '':
                continue

            dicCategories = {}

            # build a list of categories and their weights
            for i in range(0, self.numCats):

                entryCatMarker = line[i + 1].strip()

                # purely for debugging:
                # if dicTerm == 'to-day':
                #    print(self.catNames[i] + ': ' + entryCatMarker)

                # skip empty entry
                if entryCatMarker == '':
                    continue
                else:
                    if isfloat(entryCatMarker):
                        termWeight = float(entryCatMarker)
                        if termWeight == 0:
                            continue
                        else:
                            dicCategories[self.catNames[i]] = termWeight
                    elif isinteger(entryCatMarker):
                        termWeight = int(entryCatMarker)
                        if termWeight == 0:
                            continue
                        else:
                            dicCategories[self.catNames[i]] = termWeight
                    else:
                        dicCategories[self.catNames[i]] = int(1)

            # purely for debugging:
            # if dicTerm == 'to-day':
            #    print(dicCategories)
            self.UpdateCategories(dicTerm=dicTerm, newCategories=dicCategories, verbose=False)

        if verbose:
            print('Dictionary loaded.')
        return

    def ExportDict2007Format(self, dicOutFilename='Current Dictionary - 2007 Format.dic', fileEncoding='utf-8',
                             separateDicts=False, separateDictsFolder='Current Dictionary - Separate Dicts/'):
        """Exports a copy of the currently-loaded dictionary into 2007/2015 format.
           Note that the parameter 'separateDicts' asks for a *folder* name, and not a filename,
           which will be used if 'separateDicts==True' — this will then export each category
           as its own dictionary"""

        create_export_dir(dicOutFilename)

        with open(dicOutFilename, 'w', encoding=fileEncoding, newline='') as fout:
            fout.write(self.DictToString2007())

        dictCounter = 0

        if separateDicts:

            for dictCat in self.catNames:

                dictCounter += 1
                singleDictFilename = str(dictCounter).zfill(3) + '_' + dictCat + '.dic'

                create_export_dir(os.path.join(separateDictsFolder, singleDictFilename))

                with open(os.path.join(separateDictsFolder, singleDictFilename), 'w',
                          encoding=fileEncoding, newline='') as fout:
                    fout.write('%\r\n')
                    fout.write(str(dictCounter) + '\t' + dictCat)
                    fout.write('\r\n%')

                    dicTerms = self.GetSortedTermList(list(self.dictTermCatMap.keys()))

                    dicTermsForCat = set([])
                    for dicTerm in dicTerms:

                        if dictCat in self.dictTermCatMap[dicTerm].keys():
                            dicTermsForCat.add(dicTerm)

                    dicTermsForCat = self.GetSortedTermList(list(dicTermsForCat))

                    for term in dicTermsForCat:
                        fout.write('\r\n' + term + '\t' + str(dictCounter))

        print('Dictionary exported to LIWC2007 format.')

    def ExportDict2022Format(self, dicOutFilename='Current Dictionary - 2022 Format.dicx', fileEncoding='utf-8',
                             separateDicts=False, separateDictsFolder='Current Dictionary - Separate Dicts/',
                             friendlyVarNames=False, useHierarchicalCatNames=False, omitCategories=[]):
        """Exports a copy of the currently-loaded dictionary in LIWC-22 format."""

        create_export_dir(dicOutFilename)
        with open(dicOutFilename, 'w', encoding=fileEncoding, newline='') as fout:
            fout.write(self.DictToString2022(useHierarchicalCatNames, omitCategories))

        print('Dictionary exported to LIWC-22 format.')

        if separateDicts:

            if not os.path.exists(separateDictsFolder):
                os.mkdir(separateDictsFolder)

            dictCounter = 1

            for catName in self.catNames:

                dictString = '%\n1\t' + catName + '\n%\na\t1'

                singleDict = ContentCodingDictionary(dicFilename='', fileEncoding='utf-8', fromString=True,
                                                     dictString=dictString, \
                                                     dictFormat='2007', abbreviations={}, verbose=False)

                catWeights = {catName: 1.0}

                singleDict.UpdateCategories('a', catWeights, False)
                singleDict.UpdateCategories('a', {}, False)

                existingCatNames = set([])
                existingCatNames.add(catName)

                for dicTerm in self.dictTermCatMap.keys():
                    if catName in self.dictTermCatMap[dicTerm].keys():

                        catNameForIndividualTerm = dicTerm

                        if friendlyVarNames:
                            catNameForIndividualTerm = re.sub("[^0-9a-zA-Z]", "_", dicTerm)

                        if (catNameForIndividualTerm in existingCatNames):
                            catNameAddition = 1
                            tempCatName = catNameForIndividualTerm + '_' + str(catNameAddition)
                            while tempCatName in existingCatNames:
                                catNameAddition += 1
                                tempCatName = catNameForIndividualTerm + '_' + str(catNameAddition)
                            catNameForIndividualTerm = tempCatName

                        existingCatNames.add(catNameForIndividualTerm)

                        catWeights = {catName: 1.0,
                                      catNameForIndividualTerm: 1.0}

                        singleDict.UpdateCategories(dicTerm, catWeights, False)

                singleDictFilename = str(dictCounter).zfill(3) + '_' + catName + '.dicx'
                singleDictFilename = os.path.join(separateDictsFolder, singleDictFilename)

                with open(singleDictFilename, 'w', encoding=fileEncoding, newline='') as fout:
                    fout.write(singleDict.DictToString2022(useHierarchicalCatNames=False, omitCategories=[]))

                dictCounter += 1

        return

    def ExportDictJSON(self, dicOutFilename, fileEncoding, indent=4):
        """Exports the category mapping as a JSON file."""
        create_export_dir(dicOutFilename)
        with open(dicOutFilename, 'w', encoding=fileEncoding) as fout:
            json.dump(self.dictTermCatMap, fout, ensure_ascii=False, indent=indent)

        print('Exported dictionary as JSON.')
        return

    def ExportCategoryMap(self, filename='Current Dictionary - Category Map.csv', fileEncoding='utf-8-sig') -> None:
        """Exports a CSV file that shows which categories a word belongs to."""
        create_export_dir(filename)
        with open(filename, 'w', encoding=fileEncoding, newline='') as fout:
            csvw = csv.writer(fout)

            csvw.writerow(['dicTerm', 'categories'])
            dicTerms = self.GetSortedTermList(list(self.dictTermCatMap.keys()))

            for dicTerm in dicTerms:

                dicTermCats = []
                for cat in self.catNames:
                    if cat in self.dictTermCatMap[dicTerm].keys():
                        dicTermCats.append(cat)

                csvw.writerow([dicTerm, ', '.join(dicTermCats)])

        print('Exported category map.')
        return

    def DictToString2007(self, ) -> str:
        """Returns a copy of the currently-loaded dictionary as a string."""

        dictString = ''

        dictString += '%\r\n'
        for cat in self.catNames:
            dictString += str(self.catOrder[cat] + 1) + '\t' + cat + '\r\n'
        dictString += '%'

        dicTerms = self.GetSortedTermList(list(self.dictTermCatMap.keys()))

        for dicTerm in dicTerms:

            lineToWrite = '\r\n' + dicTerm
            catsForTerm = []

            for mappedCat in self.dictTermCatMap[dicTerm].keys():
                catsForTerm.append(self.catOrder[mappedCat] + 1)

            catsForTerm.sort()
            lineToWrite += '\t' + '\t'.join(str(item) for item in catsForTerm)
            dictString += lineToWrite

        return dictString

    def DictToString2022(self, useHierarchicalCatNames=False, omitCategories=[]) -> str:
        """Returns a copy of the currently-loaded dictionary as a string."""

        dictString = io.StringIO()

        csvWriter = csv.writer(dictString)
        header = ["DicTerm"]
        catsToOmit = set(omitCategories)

        catNamesAfterOmissions = self.catNames.copy()

        for cat in catsToOmit:
            catNamesAfterOmissions.remove(cat)

        catOrderAfterOmissions = {}
        for i in range(0, len(catNamesAfterOmissions)):
            catOrderAfterOmissions[catNamesAfterOmissions[i]] = i

        for cat in self.catNames:

            if cat not in catsToOmit:
                if useHierarchicalCatNames:
                    header.append(self.catNamesHierarchical[cat])
                else:
                    header.append(cat)

        csvWriter.writerow(header)

        dicTerms = self.GetSortedTermList(list(self.dictTermCatMap.keys()))

        weightedDict = False
        # first, see if we're working with a weighted dictionary or not
        for dicTerm in dicTerms:
            for cat in self.dictTermCatMap[dicTerm].keys():
                if self.dictTermCatMap[dicTerm][cat] != 1:
                    weightedDict = True
                    break

            if weightedDict == True:
                break

        # now, we actually go and write it out
        for dicTerm in dicTerms:

            lineToWrite = [''] * (self.numCats + 1)
            lineToWrite[0] = dicTerm

            for cat in self.dictTermCatMap[dicTerm].keys():

                if cat in catsToOmit:
                    continue

                outputColumn = catOrderAfterOmissions[cat]

                if weightedDict:
                    lineToWrite[outputColumn + 1] = str(self.dictTermCatMap[dicTerm][cat])
                else:
                    lineToWrite[outputColumn + 1] = "X"

            csvWriter.writerow(lineToWrite)

        return dictString.getvalue()

    def ExportDictPosterFormat(self, dicOutFilename, fileEncoding):
        """Exports a copy of the currently-loaded dictionary as a 'poster' formatted spreadsheet."""

        create_export_dir(dicOutFilename)

        posterArrays = []
        for cat in self.catNames:
            posterArrays.append([cat])

        dicTerms = self.GetSortedTermList(list(self.dictTermCatMap.keys()))

        for dicTerm in dicTerms:
            for cat in self.dictTermCatMap[dicTerm]:
                posterArrays[self.catOrder[cat]].append(dicTerm)

        rotatedList = list(map(list, zip_longest(*posterArrays, fillvalue=None)))

        with open(dicOutFilename, 'w', encoding=fileEncoding, newline='') as fout:
            csvWriter = csv.writer(fout)
            for row in rotatedList:
                csvWriter.writerow(row)

        print('Dictionary exported to poster format.')

    def ExportAsteriskOverlaps(self, filename, fileEncoding='utf-8-sig'):
        """Exports a list of all terms in the currently-loaded dictionary that overlap
        with other terms. For example, if your dictionary has both 'think' and 'think*'
        then there is a conceptual overlap."""

        create_export_dir(filename)

        print('Checking for asterisk overlaps...')

        with open(filename, 'w', encoding=fileEncoding, newline='') as fout:
            csvw = csv.writer(fout)
            csvw.writerow(['Wildcard', 'WildcardCats', 'Overlaps', 'OverlapCats', 'OverlapUniqueCats'])

            listOfDicTerms = self.GetSortedTermList(list(self.dictTermCatMap.keys()))
            listOfDicTermsWild = [dicTerm for dicTerm in listOfDicTerms if containsWildcard(dicTerm)]

            for dicTerm in listOfDicTermsWild:
                regWord = compileWildcard(dicTerm)

                for wordCompare in listOfDicTerms:
                    if wordCompare == dicTerm:
                        continue

                    if (dicTerm.replace('*', '') == wordCompare) or (bool(regWord.search(wordCompare)) == True):

                        wildcardCats = set([])
                        overlapCats = set([])
                        overlapUniqueCats = set([])

                        # get a list of all categories covered by these terms
                        wildcardCats = set(list(self.dictTermCatMap[dicTerm].keys()))
                        overlapCats = set(list(self.dictTermCatMap[wordCompare].keys()))

                        for cat in list(self.dictTermCatMap[wordCompare].keys()):
                            if cat not in wildcardCats:
                                overlapUniqueCats.add(cat)

                        csvw.writerow([dicTerm,
                                       ', '.join(list(wildcardCats)),
                                       wordCompare,
                                       ', '.join(list(overlapCats)),
                                       ', '.join(list(overlapUniqueCats))])

        print('Asterisk overlaps exported.')

        return

    def UpdateCategories(self, dicTerm='', newCategories={}, verbose=True):
        """Allows us to modify individual words within the dictionary and assign them to a new set of categories.
        Note that whatever categories you use for 'newCategories' will be the only categories that dicTerm gets
        assigned to. That is, this function will remove the dicTerm from any category not listed in newCategories.
        Right now, this will only assign weights of 1.0. This should be updated later to allow for more flexibility."""

        dicTermClean = ' '.join(dicTerm.strip().split())

        if dicTermClean == '':
            if verbose: print('Your dictionary term parameter is an empty string. No action has been taken.')
            return

        numWords = len(dicTermClean.strip().split())
        if numWords > self.maxWords: self.maxWords = numWords

        if numWords not in self.dictDataStandard.keys():
            self.dictDataStandard[numWords] = set([])

        if numWords not in self.dictDataWildsList.keys():
            self.dictDataWildsList[numWords] = []

        dicTermWild = containsWildcard(dicTermClean)

        # if we're not assigning the dicTerm to any categories at all, we can "pop" it from everything.
        if len(newCategories.keys()) == 0:
            if dicTermClean in self.dictTermCatMap.keys():
                self.dictTermCatMap.pop(dicTermClean)

                # if it's a wildcard term, we need to remove it from a couple of places
                if dicTermWild:
                    self.dictDataWildsRegEx.pop(dicTermClean)
                    self.dictDataWildsList[numWords].remove(dicTermClean)
                    self.numberOfWildcards = self.numberOfWildcards - 1
                # if it's a regular term, then we can drop it from the one place it's in
                else:
                    self.dictDataStandard[numWords].remove(dicTermClean)

            # we have to make sure to update the max words if we're removing stuff
            self.maxWords = -1
            for entry in self.dictTermCatMap.keys():
                wordLen = len(entry.strip().split())
                if wordLen > self.maxWords: self.maxWords = wordLen

            if verbose: print('Removed "' + dicTermClean + '" from the dictionary.')
            return

        # if we're assigning to a category set, then we have our work cut out for us
        else:

            removedFromCategories = []
            addedToCategories = []
            unchangedCategories = []

            if dicTermClean not in self.dictTermCatMap.keys():
                self.dictTermCatMap[dicTermClean] = {}
                if dicTermWild: self.numberOfWildcards += 1

            currentCats = list(self.dictTermCatMap[dicTermClean].keys())

            # remove term from all of the categories that aren't in the update list
            for cat in currentCats:
                if cat not in newCategories.keys():
                    # no matter what, we want to drop this from the category map for this term
                    self.dictTermCatMap[dicTermClean].pop(cat)
                    removedFromCategories.append(cat)

            # add all of the new categories
            for cat in newCategories.keys():

                if cat in self.dictTermCatMap[dicTermClean].keys():
                    unchangedCategories.append(cat)
                    continue

                else:

                    addedToCategories.append(cat)

                    # if they're trying to add the term to a category that doesn't exist,
                    # we have got to add that category.
                    if cat not in self.catNames:
                        if verbose: print('The category "' + cat + '" is not in the current dictionary.'
                                                                   ' Adding category...')
                        self.catNames.append(cat)
                        self.catOrder[cat] = len(self.catOrder.keys())
                        self.numCats += 1

                    if (dicTermWild) and (dicTermClean not in self.dictDataWildsList[numWords]):
                        self.dictDataWildsList[numWords].append(dicTermClean)
                        self.dictDataWildsRegEx[dicTermClean] = compileWildcard(dicTermClean)

                    elif (dicTermClean not in self.dictDataStandard[numWords]):
                        # since we have already established that this contains NO wildcards,
                        # we should replace any instance of \* with just the plain old asterisk,
                        # since that's what we're actually going to be coding for
                        self.dictDataStandard[numWords].add(dicTermClean)

                    self.dictTermCatMap[dicTermClean][cat] = newCategories[cat]

            if dicTermWild:
                self.SortWildcardList_numWords(numWords)

        if verbose:
            print('Your categories have been updated for "' + dicTermClean + '": ')
            if len(addedToCategories) > 0: print('\tAdded to: ' + ', '.join(addedToCategories))
            if len(removedFromCategories) > 0: print('\tRemoved from: ' + ', '.join(removedFromCategories))
            if len(unchangedCategories) > 0: print('\tUnchanged: ' + ', '.join(unchangedCategories))

        return

    def ImposeHierarchy(self, hierarchy, verbose=False, updateHierarchicalCatNames=False):
        '''This function will take lower-level categories and make sure that they
        are cross-categorized into higher-level categories. Note that this function
        does *not* remove dictionary terms from categories that are not specified
        in the hierarchy provided by users (as would be done with UpdateCategories()).'''

        hierarchyClean = hierarchy.strip().split('/')
        hierarchyClean = [cat.strip() for cat in hierarchyClean]
        hierarchyClean.reverse()
        hierarchyClean = [cat for cat in hierarchyClean if cat != '']

        if verbose: print('Imposing hierarchy: ' + ' -> '.join(hierarchyClean))

        for cat in hierarchyClean:
            if cat not in self.catNames: print('\t"' + cat + '" is not a recognized category. Omitting...')
        hierarchyClean = [cat for cat in hierarchyClean if cat in self.catNames]

        if len(hierarchyClean) < 2:
            print('\tYour hierarchy needs at least 2 levels to be imposed.')
            return

        if updateHierarchicalCatNames == True:
            tempHierarchyForward = hierarchyClean.copy()
            tempHierarchyForward.reverse()
            if tempHierarchyForward[-1] in self.catNamesHierarchical:
                self.catNamesHierarchical[tempHierarchyForward[-1]] = '|'.join(tempHierarchyForward)

        # for each word in the dictionary...
        for dicTerm in self.dictTermCatMap.keys():

            # for each lower-level category in the hierarchy...
            for i in range(0, len(hierarchyClean) - 1):
                if hierarchyClean[i] in self.dictTermCatMap[dicTerm].keys():

                    # for each higher-level category in the hierarchy...
                    for j in range(i + 1, len(hierarchyClean)):
                        if hierarchyClean[j] not in self.dictTermCatMap[dicTerm].keys():
                            self.dictTermCatMap[dicTerm][hierarchyClean[j]] = \
                                self.dictTermCatMap[dicTerm][hierarchyClean[i]]

                            # purely for debugging
                            if verbose: print('\t' + dicTerm + ' mapped from ' + hierarchyClean[i] +
                                              ' into ' + hierarchyClean[j])

        if verbose: print('Hierarchy imposed: ' + ' -> '.join(hierarchyClean))
        return

    def WeightHierarchy(self, hierarchy, exclude_onegrams):
        '''Allows you to more accurately filter weights in an upward fashion.
        Takes a python dictionary as input, where the key is the top-level
        category and the value is a list of *immediately* subordinate categories.'''

        topLevelCat = hierarchy.key()
        subordinateCats = set(hierarchy[topLevelCat])

        for dicTerm in self.dictTermCatMap.keys():

            if exclude_onegrams:
                numWords = len(dicTerm.split())
                if numWords == 1:
                    continue

            foundSubordinates = False

            if topLevelCat in self.dictTermCatMap[dicTerm]:
                categories = list(self.dictTermCatMap[dicTerm].keys())

                catWeights = {topLevelCat: 0.0}

                for cat in categories:
                    catWeights[cat] = self.dictTermCatMap[dicTerm][cat]
                    if cat in subordinateCats:
                        topLevelCat += self.dictTermCatMap[dicTerm][cat]
                        foundSubordinates = True

                if foundSubordinates == False:
                    catWeights[topLevelCat] = self.dictTermCatMap[dicTerm][topLevelCat]

            self.UpdateCategories(dicTerm=dicTerm, newCategories=catWeights, verbose=False)

    def GetSortedTermList(self, dicTermList) -> list:
        '''Provides a rule-appropriate list of terms of the dictionary'''

        termList = dicTermList.copy()
        termList.sort()

        # relocate words that start with wildcards to the end
        termListWildcardStarts = []

        for i in range(0, len(termList)):
            if termList[i].startswith('*'):
                termListWildcardStarts.append(termList[i])

        for term in termListWildcardStarts:
            termList.remove(term)

        termList.extend(termListWildcardStarts)

        return termList

    def SortWildcardList_AllWords(self) -> None:
        for numWords in range(self.maxWords, 0, -1):
            self.SortWildcardList_numWords(numWords)

        return

    def SortWildcardList_numWords(self, numWords) -> None:

        dictForSorting = {}
        dictForSorting_wordsBeginningWithWilds = {}

        maxLength = 0

        # let's go through and sort this fool out
        if numWords in self.dictDataWildsList.keys():

            for wordIndex in range(0, len(self.dictDataWildsList[numWords])):

                dicTermLength = len(self.dictDataWildsList[numWords][wordIndex])
                if dicTermLength > maxLength: maxLength = dicTermLength

                # because we are going to want to put all words that *start* with wildcards at the end of the list, we
                # do that here and set them aside.
                if self.dictDataWildsList[numWords][wordIndex].startswith('*'):
                    # make sure that we have a dictionary key for the length of this particular dictionary word
                    # for the length of this particular dictionary word
                    if (dicTermLength not in dictForSorting_wordsBeginningWithWilds.keys()):
                        dictForSorting_wordsBeginningWithWilds[dicTermLength] = []
                    dictForSorting_wordsBeginningWithWilds[dicTermLength].append(
                        self.dictDataWildsList[numWords][wordIndex])

                # otherwise, we do the same thing, but in a normal dictionary for all other terms
                else:
                    # make sure that we have a dictionary key for the length of this particular dictionary word
                    if (dicTermLength not in dictForSorting.keys()):
                        dictForSorting[dicTermLength] = []
                    dictForSorting[dicTermLength].append(self.dictDataWildsList[numWords][wordIndex])

            # we're going to use this to feed back into the original dictionary
            sortedDictTerms = []
            sortedDictTerms_wordsBeginningWithWilds = []

            # now that we've separated out all of the dictionary terms by how long they
            # are (and whether they start with a wildcard), we can go through and sort them all alphabetically

            for wordLength in range(maxLength, 0, -1):

                # we do *not* want to sort these alphabetically, because we're prioritizing dictionary ordering over
                # alphabetization. so, they're already "ordered" correctly within any given string length
                if wordLength in dictForSorting.keys(): sortedDictTerms.extend(dictForSorting[wordLength])
                if wordLength in dictForSorting_wordsBeginningWithWilds.keys():
                    sortedDictTerms_wordsBeginningWithWilds.extend(dictForSorting_wordsBeginningWithWilds[wordLength])

            # append the words beginning with wildcards on to the end of the list
            sortedDictTerms.extend(sortedDictTerms_wordsBeginningWithWilds)

            self.dictDataWildsList[numWords] = sortedDictTerms

        return


# used while reading in the dictionary
# to check for weighted dictionary
def isfloat(value):
    try:
        float(value)

        if float(value) != int(value):
            return True
        else:
            return False

    except ValueError:
        return False

def isinteger(value):
    try:
        int(value)

        if float(value) == int(value):
            return True
        else:
            return False

    except ValueError:
        return False


def containsWildcard(dicTerm):
    return bool(containsWildcardRegex.search(dicTerm))


def compileWildcard(dicTerm):
    # if it's an escaped wildcard, we set it aside in one category
    # all other remaining asterisks are going to be swapped for wildcards then
    # now, let's escape literally everything else
    # put the escaped wildcards back in
    # put the actual wildcards back in

    compiledTerm = re.compile(r'^' +
                              re.escape(dicTerm.replace(r'\*',
                                                        r'ESCAPEDASTERISKREPLACEMELATER')
                                        .replace(r'*', r'WILDCARDASTERISKREPLACEMELATER'))
                              .replace(r'ESCAPEDASTERISKREPLACEMELATER', r'\*')
                              .replace(r'WILDCARDASTERISKREPLACEMELATER', r'.*')
                              + r'$')
    return compiledTerm