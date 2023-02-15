#!/usr/bin/env python
# encoding: utf-8
# python 3.9.2
# content_coder_py
# updated on: 2023-02-14
# by Ryan L. Boyd, Ph.D.
# ryan@ryanboyd.io

import csv
import re

re._MAXCACHE = 10000

import happiestfuntokenizing
from ContentCodingDictionary import ContentCodingDictionary, containsWildcard
from create_export_dir import create_export_dir

class ContentCoder:

    def __init__(self,
                 dicFilename:str='test_files/EmpathDefaultDictionary.dic',
                 fileEncoding:str='utf-8-sig',
                 dictString:str=None,
                 dictFormat:str="2007"):

        self.PunctStopList = frozenset(["`", "´", "~", "!", "@", "#", "$", "%", "^", "&", "*",
                                        "(", ")", "_", "+", "-", "–", "=", "[", "]", "\\", ";", "'",
                                        ",", ".", "/", "{", "}", "|", ":", "\"", "<", ">", "?",
                                        "..", "...", "«", "««", "»", "»»", "“", "”", "‘", "‘‘", "’", "’’",
                                        "…", "¿", "¡", "•", "†", "‡", "°", "¦", "…"])

        self.AbbreviationList = ['ie.', 'i.e.', 'eg.', 'e.g.', 'vs.', 'ph.d.', 'phd.', 'm.d.', 'd.d.s.', 'b.a.',
                                 'b.s.', 'm.s.', 'u.s.a.', 'u.s.', 'u.t.', 'attn.', 'prof.', 'mr.', 'dr.', 'mrs.',
                                 'ms.', 'a.i.', 'a.g.i.', 'tl;dr', 't.t', 't_t']

        self.AbbreviationDict = {}

        for item in self.AbbreviationList:
            itemClean = item.replace('.', '-').replace(';', '-').replace('_', '-')

            if len(itemClean) > 2 and itemClean.endswith('-'):
                numTrailers = len(itemClean)
                itemClean = itemClean.strip('-')
                numTrailers = numTrailers - len(itemClean)
                itemClean = itemClean[:-1] + ''.join(['-'] * numTrailers) + itemClean[-1:]

            self.AbbreviationDict[item] = itemClean
            self.AbbreviationDict[item + ','] = itemClean

        self.numberPatternRegex = re.compile(r'\d+(,\d+)*(\.\d+)?')

        # if you need to use a different tokenizer, this is the place to swap it in.
        # you will also need to use the correct method in within the Analyze() function.
        self.tokenizer = happiestfuntokenizing.Tokenizer(preserve_case=False, preserve_keywords=False)

        self.capturedFreqs = {}

        if dictString is not None:

            if dictFormat not in ["2007", "2022"]:
                print('You must provide a \'dictFormat=\' argument for the dictionary contents to be parsed correctly.'
                      ' This can either be dictFormat=\'2007\' or \'2022\' to work, but the parameter must be a'
                      ' string that is one of those two values.')

                return

            self.dict = ContentCodingDictionary(dicFilename=dicFilename,
                                                fileEncoding=fileEncoding,
                                                fromString=True,
                                                dictString=dictString,
                                                dictFormat=dictFormat,
                                                abbreviations=self.AbbreviationDict)

        else:
            self.dict = ContentCodingDictionary(dicFilename=dicFilename,
                                                fileEncoding=fileEncoding,
                                                abbreviations=self.AbbreviationDict)

        # now that the dictionary is loaded, let's bump up the maximum
        # number of compiled regular expressions that we are caching to
        # speed things along. We give it 5% overhead on our regexes that
        # we have here, just in case.
        if int(self.dict.numberOfWildcards * 1.05) > re._MAXCACHE:
            re._MAXCACHE = int(self.dict.numberOfWildcards * 1.05)

    def GetResultsHeader(self):
        """Returns a list of all output categories. Useful as the header row of a CSV file."""

        headerArray = ['WC', 'Dic', 'BigWords', 'Numbers']

        for cat in self.dict.catNames:
            headerArray.append(cat)

        headerArray.append('AllPunct')
        headerArray.append('Period')
        headerArray.append('Comma')
        headerArray.append('QMark')
        headerArray.append('Exclam')
        headerArray.append('Apostro')

        return headerArray

    def GetResultsArray(self, resultsDICT, rounding=4):
        """Takes the output of self.Analyze() and formats it as a list. Useful for formatting output for CSV writing."""

        resultsArray = []
        resultsArray.append(resultsDICT['WC'])

        resultsArray.append(normal_round(resultsDICT['Dic'], rounding))
        resultsArray.append(normal_round(resultsDICT['BigWords'], rounding))
        resultsArray.append(normal_round(resultsDICT['Numbers'], rounding))

        for cat in self.dict.catNames:
            resultsArray.append(normal_round(resultsDICT[cat], rounding))

        resultsArray.append(normal_round(resultsDICT['AllPunct'], rounding))
        resultsArray.append(normal_round(resultsDICT['Period'], rounding))
        resultsArray.append(normal_round(resultsDICT['Comma'], rounding))
        resultsArray.append(normal_round(resultsDICT['QMark'], rounding))
        resultsArray.append(normal_round(resultsDICT['Exclam'], rounding))
        resultsArray.append(normal_round(resultsDICT['Apostro'], rounding))

        return resultsArray

    def __RetainFrequency(self, dicTerm, capturedString):
        """Stores/keeps the frequencies of captured terms. Should not be called outside of ContentCoder class."""

        if dicTerm not in self.capturedFreqs.keys():
            self.capturedFreqs[dicTerm] = {}

        if capturedString in self.capturedFreqs[dicTerm].keys():
            self.capturedFreqs[dicTerm][capturedString] += 1
        else:
            self.capturedFreqs[dicTerm][capturedString] = 1

        return

    def FillCaptureGaps(self):

        listOfKeys = list(self.dict.dictTermCatMap.keys())

        for dicTerm in listOfKeys:
            if dicTerm not in self.capturedFreqs.keys():
                self.capturedFreqs[dicTerm] = {'': 0}

        return

    def ExportCaptures(self,
                       filename: str,
                       fileEncoding:str='utf-8-sig',
                       wildcardsOnly:bool=False,
                       fullset:bool=True):
        """"If you've been aggregating the frequencies of captured words, this will export that list."""

        if len(self.capturedFreqs.keys()) == 0:
            print('\t!!! There are no terms in your frequency list. !!!\n\t!!! Did you remember to'
                  ' set \'retainFreqs\' to True? !!!')
            return

        listOfKeys = list(self.dict.dictTermCatMap.keys())

        self.FillCaptureGaps()

        listOfKeys.sort()

        if wildcardsOnly:
            listOfKeys = [x for x in listOfKeys if containsWildcard(x)]

        create_export_dir(filename)
        with open(filename, 'w', encoding=fileEncoding, newline='') as fout:
            csvw = csv.writer(fout)
            csvw.writerow(['dicTerm', 'captured', 'count', 'categories'])

            for dicTerm in listOfKeys:

                listOfCaptures = list(self.capturedFreqs[dicTerm])
                listOfCaptures.sort()

                for capture in listOfCaptures:

                    # skip to the next term if we're not exporting the fullset
                    if fullset == False and capture == '':
                        continue

                    csvw.writerow([dicTerm,
                                   capture,
                                   str(self.capturedFreqs[dicTerm][capture]),
                                   ', '.join(self.dict.dictTermCatMap[dicTerm])])

        print('Exported captured word frequencies.')

        return

    def Analyze(self,
                inputText:str,
                relativeFreq=True,
                dropPunct=True,
                retainCaptures=False,
                returnTokens=False,
                wildcardMem=True):
        """Analyze a string and return the results."""

        resultsRawFreq = {}
        resultsRelativeFreq = {}

        resultsRawFreq['Dic'] = int(0)
        resultsRelativeFreq['Dic'] = 0.0

        resultsRawFreq['WC'] = int(0)
        resultsRelativeFreq['WC'] = int(0)

        resultsRawFreq['BigWords'] = int(0)
        resultsRelativeFreq['BigWords'] = 0.0

        resultsRawFreq['Numbers'] = int(0)
        resultsRelativeFreq['Numbers'] = 0.0

        resultsRawFreq['AllPunct'] = int(0)
        resultsRelativeFreq['AllPunct'] = 0.0
        resultsRawFreq['Period'] = int(0)
        resultsRelativeFreq['Period'] = 0.0
        resultsRawFreq['Comma'] = int(0)
        resultsRelativeFreq['Comma'] = 0.0
        resultsRawFreq['QMark'] = int(0)
        resultsRelativeFreq['QMark'] = 0.0
        resultsRawFreq['Exclam'] = int(0)
        resultsRelativeFreq['Exclam'] = 0.0
        resultsRawFreq['Apostro'] = int(0)
        resultsRelativeFreq['Apostro'] = 0.0

        for cat in self.dict.catNames:
            resultsRawFreq[cat] = int(0)
            resultsRelativeFreq[cat] = 0.0

        resultsRawFreq['Period'] = inputText.count('.')
        resultsRawFreq['Comma'] = inputText.count(',')
        resultsRawFreq['QMark'] = inputText.count('?')
        resultsRawFreq['Exclam'] = inputText.count('!')
        resultsRawFreq['Apostro'] = inputText.count('\'') + inputText.count('’')

        for punctItem in list(self.PunctStopList):
            if len(punctItem) == 1:
                resultsRawFreq['AllPunct'] += inputText.count(punctItem)

        # preprocess the text so that we can handle whatever we need to handle
        preprocessedText = self.PreprocessText(inputText)

        # count numbers within the text
        numberCount = len(self.numberPatternRegex.findall(preprocessedText))
        # print('Numbers: ' + str(numberCount))

        tokens = self.tokenizer.tokenize(preprocessedText)
        # remove stop words
        tokensNoPunct = [x for x in tokens if x not in self.PunctStopList]

        if dropPunct:
            tokens = tokensNoPunct.copy()

        totalStringLengthNoPunct = len(tokensNoPunct)
        totalStringLength = len(tokens)

        resultsRawFreq['WC'] = int(totalStringLengthNoPunct)
        resultsRelativeFreq['WC'] = int(totalStringLengthNoPunct)

        singleWordRelFreqValue = 0.0
        if totalStringLengthNoPunct > 0:
            singleWordRelFreqValue = (1.0 / int(totalStringLengthNoPunct)) * 100

        for token in tokens:
            if len(token) > 6:
                resultsRawFreq['BigWords'] += int(1)
                resultsRelativeFreq['BigWords'] += singleWordRelFreqValue

        if resultsRawFreq['WC'] > 0
            resultsRelativeFreq['AllPunct'] = resultsRawFreq['AllPunct'] / resultsRawFreq['WC']
            resultsRelativeFreq['Period'] = resultsRawFreq['Period'] / resultsRawFreq['WC']
            resultsRelativeFreq['Comma'] = resultsRawFreq['Comma'] / resultsRawFreq['WC']
            resultsRelativeFreq['QMark'] = resultsRawFreq['QMark'] / resultsRawFreq['WC']
            resultsRelativeFreq['Exclam'] = resultsRawFreq['Exclam'] / resultsRawFreq['WC']
            resultsRelativeFreq['Apostro'] = resultsRawFreq['Apostro'] / resultsRawFreq['WC']

        # last thing for us to do is make sure that any word with an asterisk in it has that
        # asterisk escaped. we do this after we count BigWords just so we don't throw things off
        tokens = [x.replace('*', r'\*') for x in tokens]

        # let's go through and start analyzing!
        for i in range(0, totalStringLength):
            for numberOfWords in range(self.dict.maxWords, 0, -1):

                # make sure that we don't overextend past our array
                if (i + numberOfWords > totalStringLength):
                    continue

                # build the string that we're looking to analyze
                targetString = ''

                if (numberOfWords > 1):
                    targetString = ' '.join(tokens[i:i + numberOfWords])
                else:
                    targetString = tokens[i]

                # looking for a perfect, literal match
                if targetString in self.dict.dictDataStandard[numberOfWords]:

                    resultsRawFreq['Dic'] += numberOfWords
                    resultsRelativeFreq['Dic'] += numberOfWords * singleWordRelFreqValue

                    # increment frequencies for all of the categories associated with this term
                    # note that we replace asterisk here with an escaped asterisk because,
                    # we we're not looking at a wildcard entry, the asterisk will NOT be
                    # escaped in self.dict.dictDataStandard[numberOfWords], but it WILL
                    # still be escaped everywhere else in the dictionary
                    for cat in self.dict.dictTermCatMap[targetString].keys():
                        incrementValue = numberOfWords * self.dict.dictTermCatMap[targetString][cat]
                        resultsRawFreq[cat] += incrementValue
                        resultsRelativeFreq[cat] += incrementValue * singleWordRelFreqValue

                    # if we're retaining frequencies, we do that here
                    if retainCaptures:
                        self.__RetainFrequency(targetString, targetString)

                    # make sure that we move along, little doggy
                    i += numberOfWords - 1
                    break

                # if we're using wildcard memory, this will help speed up previously-identified captures
                elif wildcardMem and numberOfWords in self.dict.wildcardMemory and \
                        targetString in self.dict.wildcardMemory[numberOfWords].keys():

                    wildcardEntry = self.dict.wildcardMemory[numberOfWords][targetString]

                    resultsRawFreq['Dic'] += numberOfWords
                    resultsRelativeFreq['Dic'] += numberOfWords * singleWordRelFreqValue

                    # increment frequencies for all of the categories associated with this term
                    for cat in self.dict.dictTermCatMap[wildcardEntry].keys():
                        incrementValue = numberOfWords * self.dict.dictTermCatMap[wildcardEntry][cat]
                        resultsRawFreq[cat] += incrementValue
                        resultsRelativeFreq[cat] += incrementValue * singleWordRelFreqValue

                    # if we're retaining frequencies, we do that here
                    if retainCaptures:
                        self.__RetainFrequency(wildcardEntry, targetString)

                    # make sure that we move along, little doggy
                    i += numberOfWords - 1
                    break

                # here, we do the wildcard stuff
                else:
                    for wildcardEntry in self.dict.dictDataWildsList[numberOfWords]:

                        # test the wildcard:
                        if len(self.dict.dictDataWildsRegEx[wildcardEntry].findall(targetString)) > 0:

                            resultsRawFreq['Dic'] += numberOfWords
                            resultsRelativeFreq['Dic'] += numberOfWords * singleWordRelFreqValue

                            if wildcardMem: self.dict.wildcardMemory[numberOfWords][targetString] = wildcardEntry

                            # increment frequencies for all of the categories associated with this term
                            for cat in self.dict.dictTermCatMap[wildcardEntry].keys():
                                incrementValue = numberOfWords * self.dict.dictTermCatMap[wildcardEntry][cat]
                                resultsRawFreq[cat] += incrementValue
                                resultsRelativeFreq[cat] += incrementValue * singleWordRelFreqValue

                            # if we're retaining frequencies, we do that here
                            if retainCaptures:
                                self.__RetainFrequency(wildcardEntry, targetString)

                            # make sure that we move along, little doggy
                            i += numberOfWords - 1
                            break

        # add in numbers, if that's what we're doing
        resultsRawFreq, resultsRelativeFreq = self.AddNumbers(resultsRawFreq, resultsRelativeFreq,
                                                              numberCount, singleWordRelFreqValue)

        if relativeFreq:
            if returnTokens:
                resultsRelativeFreq['tokenizedText'] = tokens
            return resultsRelativeFreq
        else:
            if returnTokens:
                resultsRawFreq['tokenizedText'] = tokens
            return resultsRawFreq

    def PreprocessText(self, inputText):
        '''Cleans up text prior to processing.'''
        textSplit = inputText.lower().strip().split()

        # handle those little abbreviations
        for i in range(0, len(textSplit)):
            if textSplit[i] in self.AbbreviationDict.keys():
                textSplit[i] = self.AbbreviationDict[textSplit[i]]

        text = ' '.join(textSplit)
        return text

    def AddNumbers(self, resultsRawFreq, resultsRelativeFreq, numberCount, singleWordRelFreqValue):

        resultsRawFreq['Numbers'] += numberCount
        resultsRelativeFreq['Numbers'] += numberCount * singleWordRelFreqValue

        return resultsRawFreq, resultsRelativeFreq





# we need this to correctly round
def normal_round(num, ndigits=0):
    """
    Rounds a float to the specified number of decimal places.
    num: the value to round
    ndigits: the number of digits to round to
    """
    if ndigits == 0:
        return int(num + 0.5)
    else:
        digit_value = 10 ** ndigits
        return int(num * digit_value + 0.5) / digit_value


if __name__ == '__main__':
    testString = """And on the subject of burning books:
                I want to congratulate librarians, not famous for their physical
                 strength or their powerful political connections or their great
                 wealth, who, all over this country, have staunchly resisted
                 anti-democratic bullies who have tried to remove certain books
                 from their shelves, and have refused to reveal to thought police
                 the names of persons who have checked out those titles.

                 So the America I loved still exists, if not in the White House
                 or the Supreme Court or 100 the Senate or the House of Representatives
                 or the media. The America I love still exists at the front desks
                 of our public libraries."""

    # testString = 'Welcome to the U.S.A. of American Mr. President.'

    # create a new member of the "ContentCoder()" class. In this version, we specify the
    # dictionary file that we want to load up when we make a new LIWC object
    cc = ContentCoder(dicFilename='dictionaryFile/EmpathDefaultDictionary.dic',
                      fileEncoding='utf-8-sig')



    cc_results = cc.Analyze(testString,  # the text that we want to analyze
                            relativeFreq=True,
                            # whether we want results saved as relative frequencies (False = raw frequencies)
                            dropPunct=False,  # do we want to omit punctuation while analyzing?
                            #      this can create a difference between things like:
                            #      ["I don't know."] vs. ["I ... don't know."]
                            retainCaptures=True,
                            # do we want to keep a list of which dictionary terms capture which words in the text(s)?
                            returnTokens=True,
                            # do we want to get the tokens back with the results? (including/excluding punctuation)
                            wildcardMem=True)  # do we want to keep a history of captured wildcards for faster processing of future texts?

    print(' '.join(cc_results['tokenizedText']))
    # print(cc.resultsRelativeFreq)

    # this simply gives us a CSV-style header row for the currently-loaded dictionary
    print(cc.GetResultsHeader())

    # this gives us the results that we saved earlier as a CSV-style list of data
    print(cc.GetResultsArray(resultsDICT=cc_results))

    # this exports our frequencies that we have retained during analysis
    cc.ExportCaptures(filename='results/Current Dictionary - Captured Frequencies.csv',  # filename to save to
                      wildcardsOnly=False,  # do you only want to see the words captured by wildcards?
                      fullset=True,
                      # do you want to see a complete list, including words in your dictionary that captured nothing?
                      fileEncoding='utf-8-sig')

    # this exports the word-to-category mapping in a readable fashion
    cc.dict.ExportCategoryMap(filename='results/Current Dictionary - Category Map.csv',
                              fileEncoding='utf-8-sig')

    # this line would tell us the category names for our loaded dictionary
    # print(liwc.dict.catNames)

    # this will export our currently loaded dictionary to the old LIWC2007 style formatted file
    cc.dict.ExportDict2007Format('results/Current Dictionary - 2007 Format.dic',
                                 fileEncoding='utf-8',
                                 separateDicts=True,
                                 separateDictsFolder='results/Separate 2007 Dicts/')

    # this will take the currently loaded dictionary and export it as a LIWC-22 formatted file
    # note that, officially, LIWC-22 dictionary files are encoded as utf-8 WITHOUT the BOM
    cc.dict.ExportDict2022Format('results/Current Dictionary - 2022 Format.dicx',
                                 fileEncoding='utf-8')
    cc.dict.ExportDict2022Format('results/Current Dictionary - 2022 Format.csv',
                                 fileEncoding='utf-8-sig')

    # we can also export a full-blown set of individual dictionaries that treat every
    # word as their own category within each dictionary.
    cc.dict.ExportDict2022Format('results/Current Dictionary - 2022 Format.dicx',
                                 fileEncoding='utf-8',
                                 separateDicts=True,
                                 separateDictsFolder='results/Separate 2022 Dicts/',
                                 friendlyVarNames=True)

    # this will take the currently loaded dictionary and export it as a JSON file
    cc.dict.ExportDictJSON('results/Current Dictionary - JSON.json', fileEncoding='utf-8', indent=4)

    # this will export a "poster" of the currently-loaded dictionary file.
    cc.dict.ExportDictPosterFormat('results/Current Dictionary - Poster File.csv', fileEncoding='utf-8-sig')

    # This will rebuild the dictionary as a string, using the LIWC2007 dictionary format
    LIWC2007_format_dictionary_string = cc.dict.DictToString2007()

    # This will rebuild the dictionary as a string, using the LIWC-22 dictionary format
    LIWC2022_format_dictionary_string = cc.dict.DictToString2022(useHierarchicalCatNames=True)

    # it is also possible to create a new LIWC object if you have your dictionary file loaded
    # already as a string. You simply need to make sure that you specify the "dictFormat" parameter
    # and let it know whether your string is a LIWC dictionary in the 2007 or 2022 format.

    # test the ability to load a dictionary contents from a string
    cc_liwc2007_format = ContentCoder(dictString=LIWC2007_format_dictionary_string,
                                      dictFormat='2007')

    # test the ability to load a dictionary contents from a string
    cc_liwc2022_format = ContentCoder(dictString=LIWC2022_format_dictionary_string,
                                      dictFormat='2022')

    # you can also update the categories associated with a given dictionary term. this allows
    # you to also add/remove words to your dictionary, with weights. If you add a term to a
    # category that does not exist, the category will be created for you.
    cc_liwc2022_format.dict.UpdateCategories(dicTerm='fun-times',
                                             newCategories={
                                       'posemo': 1.0,
                                       'enjoyment': 3.0
                                   })

    # this will destroy the word "fun-times" because it is no longer
    # associated with any categories. Note that categories introduced
    # (e.g., "enjoyment") are not destroyed in this process.
    cc_liwc2022_format.dict.UpdateCategories(dicTerm='fun-times',
                                             newCategories={})
