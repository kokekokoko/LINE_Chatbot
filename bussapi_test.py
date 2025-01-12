from flask import Flask, request, abort
from flask import render_template, request, redirect
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime , timedelta,time 
import jpholiday 
import pytz 
from zikokuhyou import kasugaeki, keiosinjukustation, kasumisyougakkou
import pandas as pd
import urllib.request, urllib.error
from google.transit import gtfs_realtime_pb2
from geopy.distance import geodesic 
import json 
from linebot import LineBotApi
import time as time_module
from linebot.models import TextSendMessage
# import time 

from linebot.v3 import (
    WebhookHandler
)
from linebot.v3.exceptions import (
    InvalidSignatureError
)
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage
)
from linebot.v3.webhooks import (
    MessageEvent,
    TextMessageContent
)


def isBizDay(Date):
    if Date.weekday() >= 5 or jpholiday.is_holiday(Date):
        return 1 #holiday
    else:
        return 0 #weekday
def nexttrain(time1,eki,isweekday):
    ans = []
    for zikan, hun in eki[isweekday].items():
        if time1.hour > zikan:
            continue
        elif time1.hour == zikan:
            for i in range(len(hun)):
                if len(ans) == 3:
                    return ans 
                if time1.minute <= hun[i]:
                    ans.append(datetime.combine(datetime.today(),time(zikan,hun[i])))
        elif time1.hour < zikan:
            for i in range(len(hun)):
                if len(ans) == 3:
                    return ans 
                if zikan == 24:
                    zikan = 0 
                    
                ans.append(datetime.combine(datetime.today(),time(zikan,hun[i])))
    return ans 
def geopy_distance(lat1, lon1, lat2, lon2):
    point1 = (lat1, lon1)
    point2 = (lat2, lon2)
    distance = geodesic(point1, point2).meters
    # print(distance)
    if distance <= 150:
        return True
    else:
        return False
def get_gtfs_rt():
    API_Endpoint = "https://api.odpt.org/api/v4/gtfs/realtime/odpt_NishiTokyoBus_NTBus_vehicle?acl:consumerKey=doebt5mdvzd7zaj9ne2u869izwnygjw6k8j7xs6m18xthqp7bo1v6k3l0nqcvpk3"
    feed = gtfs_realtime_pb2.FeedMessage()
    column = ["id","trip_id","route_id","direction_id","lat","lon","current_stop_sequence","timestamp","stop_id"]
    result = []
    now = datetime.now()
    now_str = now.strftime('%Y%m%dT%H%M%S')#現在時刻を文字型に変換

    with urllib.request.urlopen(API_Endpoint) as res:
        feed.ParseFromString(res.read())
        for entity in feed.entity:
                record = [
                entity.id,                            #車両ID
                entity.vehicle.trip.trip_id,          #一意に求まるルート番号
                entity.vehicle.trip.route_id,         #路線番号（≒系統）
                entity.vehicle.trip.direction_id,     #方向（上り下り）
                entity.vehicle.position.latitude,     #車両経度
                entity.vehicle.position.longitude,    #車両緯度
                entity.vehicle.current_stop_sequence, #直近で通過した停留所の発着順序
                entity.vehicle.timestamp,             #タイムスタンプ
                entity.vehicle.stop_id,               #直近で通過した停留所
                ]
                if entity.vehicle.trip.route_id in ["10009","10011", "10014", "10015"] and entity.vehicle.trip.direction_id == 1 and geopy_distance(35.70437416495755, 139.30905085675604, float(entity.vehicle.position.latitude),float(entity.vehicle.position.longitude)):
                    result.append(record)

    new_df = pd.DataFrame(result, columns=column)
    new_df["timestamp"] = pd.to_datetime(new_df.timestamp, unit='s', utc=True).dt.tz_convert('Asia/Tokyo')  # タイムスタンプ情報をUNIX時間から日本時間に変換
    new_df["timestamp"] = new_df["timestamp"].dt.tz_localize(None)  # Timezone情報を削除
    return new_df 

aqaa = 53434