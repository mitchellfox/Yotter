from flask import Markup
from requests_futures.sessions import FuturesSession
from werkzeug.datastructures import Headers
from concurrent.futures import as_completed
from numerize import numerize
from bs4 import BeautifulSoup
from re import findall
import time, datetime
import requests
import bleach
import urllib
import json
import re

##########################
#### Config variables ####
##########################
config = json.load(open('yotter-config.json'))
config['nitterInstance']

def get_user_info(username):
    response = urllib.request.urlopen('{instance}{user}'.format(instance=config['nitterInstance'], user=username)).read()
    #rssFeed = feedparser.parse(response.content)

    html = BeautifulSoup(str(response), "lxml")
    if html.body.find('div', attrs={'class':'error-panel'}):
        return False
    else:
        html = html.body.find('div', attrs={'class':'profile-card'})

        if html.find('a', attrs={'class':'profile-card-fullname'}):
            fullName = html.find('a', attrs={'class':'profile-card-fullname'}).getText().encode('latin1').decode('unicode_escape').encode('latin1').decode('utf8')
        else:
            fullName = None
        
        if html.find('div', attrs={'class':'profile-bio'}):
            profileBio = html.find('div', attrs={'class':'profile-bio'}).getText().encode('latin1').decode('unicode_escape').encode('latin1').decode('utf8')
        else:
            profileBio = None

        user = {
            "profileFullName":fullName,
            "profileUsername":html.find('a', attrs={'class':'profile-card-username'}).string.encode('latin_1').decode('unicode_escape').encode('latin_1').decode('utf8'),
            "profileBio":profileBio,
            "tweets":html.find_all('span', attrs={'class':'profile-stat-num'})[0].string,
            "following":html.find_all('span', attrs={'class':'profile-stat-num'})[1].string,
            "followers":numerize.numerize(int(html.find_all('span', attrs={'class':'profile-stat-num'})[2].string.replace(",",""))),
            "likes":html.find_all('span', attrs={'class':'profile-stat-num'})[3].string,
            "profilePic":"{instance}{pic}".format(instance=config['nitterInstance'], pic=html.find('a', attrs={'class':'profile-card-avatar'})['href'][1:])
        }
        return user

def get_tweets(user, page=1):        
    feed = urllib.request.urlopen('{instance}{user}'.format(instance=config['nitterInstance'], user=user)).read()
    #Gather feedPosts
    res = feed.decode('utf-8')
    html = BeautifulSoup(res, "html.parser")
    feedPosts = get_feed_tweets(html)

    if page == 2:
        nextPage = html.find('div', attrs={'class':'show-more'}).find('a')['href']
        print('{instance}{user}{page}'.format(instance=config['nitterInstance'], user=user, page=nextPage))
        feed = urllib.request.urlopen('{instance}{user}{page}'.format(instance=config['nitterInstance'], user=user, page=nextPage)).read()
        res = feed.decode('utf-8')
        html = BeautifulSoup(res, "html.parser")
        feedPosts = get_feed_tweets(html)
    return feedPosts

def get_feed_tweets(html):
    feedPosts = []
    userFeed = html.find_all('div', attrs={'class':'timeline-item'})
    if userFeed != []:
        for post in userFeed[:-1]:
            if 'show-more' in str(post):
                continue
            date_time_str = post.find('span', attrs={'class':'tweet-date'}).find('a')['title'].replace(",","")

            if post.find('div', attrs={'class':'pinned'}):
                if post.find('div', attrs={'class':'pinned'}).find('span', attrs={'icon-pin'}):
                    continue

            tweet = {}
            tweet['op'] = post.find('a', attrs={'class':'username'}).text
            tweet['twitterName'] = post.find('a', attrs={'class':'fullname'}).text
            tweet['timeStamp'] = str(datetime.datetime.strptime(date_time_str, '%d/%m/%Y %H:%M:%S'))
            tweet['date'] = post.find('span', attrs={'class':'tweet-date'}).find('a').text
            tweet['content'] = Markup(post.find('div',  attrs={'class':'tweet-content'}).decode_contents())
            
            if post.find('div', attrs={'class':'retweet-header'}):
                tweet['username'] = post.find('div', attrs={'class':'retweet-header'}).find('div', attrs={'class':'icon-container'}).text
                tweet['isRT'] = True
            else:
                tweet['username'] = tweet['op']
                tweet['isRT'] = False
            
            tweet['profilePic'] = config['nitterInstance']+post.find('a', attrs={'class':'tweet-avatar'}).find('img')['src'][1:]
            tweet['url'] = config['nitterInstance'] + post.find('a', attrs={'class':'tweet-link'})['href'][1:]
            
            # Is quoting another tweet
            if post.find('div', attrs={'class':'quote'}):
                tweet['isReply'] = True
                quote = post.find('div', attrs={'class':'quote'})
                if quote.find('div',  attrs={'class':'quote-text'}):
                    tweet['replyingTweetContent'] = Markup(quote.find('div',  attrs={'class':'quote-text'}))
                    
                if quote.find('a', attrs={'class':'still-image'}):
                    tweet['replyAttachedImages'] = []
                    images = quote.find_all('a',  attrs={'class':'still-image'})
                    for img in images:
                        img = BeautifulSoup(str(img), "lxml")
                        url = config['nitterInstance'] + img.find('a')['href'][1:]
                        tweet['replyAttachedImages'].append(url)

                tweet['replyingUser']=quote.find('a',  attrs={'class':'username'}).text
                post.find('div', attrs={'class':'quote'}).decompose()
            else:
                tweet['isReply'] = False
            
            # Has attatchments
            if post.find('div',  attrs={'class':'attachments'}):
                # Images
                if  post.find('div',  attrs={'class':'attachments'}).find('a', attrs={'class':'still-image'}):
                    tweet['attachedImages'] = []
                    images = post.find('div',  attrs={'class':'attachments'}).find_all('a', attrs={'class':'still-image'})
                    for img in images:
                        img = BeautifulSoup(str(img), 'lxml')
                        url = config['nitterInstance'] + img.find('a')['href'][1:]
                        tweet['attachedImages'].append(url)
                else:
                    tweet['attachedImages'] = False
                    
                if post.find('div', attrs={'gallery-video'}):
                    tweet['attachedVideo'] = True
                else:
                    tweet['attachedVideo'] = False
            else:
                tweet['attachedVideo'] = False
                tweet['attachedImages'] = False
            feedPosts.append(tweet)
    else:
        return {"emptyFeed": True}
    return feedPosts