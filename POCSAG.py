#!/usr/bin/python
# -*- coding: utf-8 -*-
# encoding=utf8  

#Für kleineres Raspi Image
#sudo apt-get install deborphan
#sudo apt-get autoremove --purge libx11-.* lxde-.* raspberrypi-artwork xkb-data omxplayer penguinspuzzle sgml-base xml-core alsa-.* cifs-.* samba-.* fonts-.* desktop-* gnome-.*
#sudo apt-get autoremove --purge $(deborphan)
#sudo apt-get autoremove --purge
#sudo apt-get autoclean
#
#Abhängigkeiten von multimon-ng
#sudo apt-get install libpulse0 libx11-6

import time
import sys
import subprocess
import os

import mysql
import mysql.connector

import re
import telepot
from pprint import pprint
import time

reload(sys)
sys.setdefaultencoding('utf8')


### rtl_fm Config
###
frequenz = 100000000
ppm = 0
decoder = 'POCSAG1200'
TelegramBotKey = '********KEY*********'

### MySQL Config
###
mysql_charset = 'utf8'
mysql_host = 'localhost'
mysql_user = 'POCSAG'
mysql_passwd = 'POCSAG'
mysql_db = 'POCSAG'

###
### Config Ende

einsatz = ''
einsatz_time = 0
messages = {}
chats = {}

def connectMySQL():
    try:
        return mysql.connector.connect(charset = mysql_charset, host = mysql_host, user = mysql_user, passwd = mysql_passwd, db = mysql_db)
    except:
        print 'Keine Verbindung zum Server'
        exit(0)

connection = connectMySQL()
cursor = connection.cursor(buffered=True)
bot = telepot.Bot(TelegramBotKey)

def handle(msg):
    cursor.execute("SELECT id, admin FROM user WHERE chat_id = %s", (str(msg['chat']['id']),))
    user = cursor.fetchone()

    if msg['text'][0] == '/' and msg['text'].startswith('/start') == False:
        cmd = msg['text'].split(' ');
        if cmd[0] == '/add' and user[1] == '1':
            sql = "insert into user (chat_id) values (%s)"
            chat_id = cmd[1].replace(' ','')
            cursor.execute(sql, (chat_id,))
            bot.sendMessage(msg['chat']['id'], 'Chat ID ('+str(cmd[1].replace(' ',''))+') hinzugefügt')
        else:
            bot.sendMessage(msg['chat']['id'], 'Keine Rechte oder das Kommando gibt es nicht :-(')
    else:
        if(cursor.rowcount > 0):
            bot.sendMessage(msg['chat']['id'], 'Du bist bereits im Verteiler :-)')
        else:    
            bot.sendMessage(msg['chat']['id'], 'Sende mir bitte folgende Nummer: '+str(msg['chat']['id']))
        pprint(msg)
    connection.commit()

bot.message_loop(handle)

def curtime():
    return time.strftime("%Y-%m-%d %H:%M:%S")

def getByRIC(ric):
    cursor.execute("SELECT wehr FROM rics WHERE ric = %s",(str(ric),))
    wehr = cursor.fetchone()
    if(cursor.rowcount > 0):
        return wehr[0]
    else:
        return 'RIC unbekannt (' + str(ric) + ')'

def getFileName():
    return 'log/POCSAG_' + str(time.strftime("%Y-%m-%d")) + '.txt'

multimon_ng = subprocess.Popen('rtl_fm -d 0 -f ' + str(frequenz) + ' -M fm -p ' + str(ppm) + ' -E DC -F 0 -l 0 -g 100 -s 22050 - | multimon-ng -t raw -a ' + decoder + ' -f alpha /dev/stdin',
                               stdout=subprocess.PIPE,
                               stderr=open('error.txt', 'a'),
                               shell=True)

try:
    while True:
        line = multimon_ng.stdout.readline()
        multimon_ng.poll()
        if line.__contains__('Alpha:'):
            with open(getFileName(), 'a') as f:
                f.write(line)

            if line.startswith('POCSAG'):
                address = line[21:28].replace(" ", "")
                subric = line[40:41].replace(' ', '').replace('3', '4').replace('2', '3').replace('1', '2').replace('0', '1')
                message = line.split('Alpha:   ')[1].strip().rstrip('').strip()

                wehr = getByRIC(address);

                print 'Alpha: ', wehr, curtime(), address, subric, message

                if line.__contains__('ENR:') and len(message) > 0:
                    message = re.sub('<[A-Z]{1,}>','',message)
                    enr = message.split('ENR:')[1].replace(" ","").strip().rstrip('').strip()

                    with open(getFileName(), 'a') as f:
                        f.write(curtime() + ' ' + wehr + ' ' + address + ' ' + subric + ' ' + message + '\n')

                    telegramMessage = u"\U0001f692 " + wehr

                    query = ("SELECT chat_id FROM user")
                    cursor.execute(query)

                    if enr != einsatz:
                        messages.clear()
                        chats.clear()
                        
                        symbol = u"\U0001f6a8"
                        if message.__contains__("TH "):
                            symbol = u"\U0001f6e0"
                        elif message.__contains__("BMA "):
                            symbol = u"\U0001f6a8"
                        elif message.__contains__("Brand "):
                            symbol = u"\U0001f525"
                        elif message.__contains__("Türnotöffnung "):
                            symbol = u"\U0001f6aa"
                        elif message.__contains__("DME "):
                            symbol = u"\U0001f4df"

                        telegramMessage = symbol + " " + message + "\n" + telegramMessage

                        einsatz = enr;

                        for (chat_id,) in cursor:
                            print 'Telegram: ', 'Nachricht an:', chat_id
                            messages[chat_id] = telegramMessage
                            chats[chat_id] = bot.sendMessage(chat_id, telegramMessage)
                    else:
                        if wehr != "Textmeldung":
                            for (chat_id,) in cursor:
                                print 'Telegram: ', 'Update Nachricht an:', chat_id
                                messages[chat_id] = messages[chat_id] + "\n" + telegramMessage
                                bot.editMessageText((chat_id, chats[chat_id]['message_id']), messages[chat_id])

                    cursor.execute("INSERT INTO meldungen (ric,funktion,text,einsatz) VALUES (%s,%s,%s,%s)",(address,subric,line,message,))
                    connection.commit()

except KeyboardInterrupt:
    cursor.close()
    connection.close()
    os.kill(multimon_ng.pid, 9)
