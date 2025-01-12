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

app = Flask(__name__)
if __name__ == "__main__":
    app.run(debug=True)
# 平日か休日かを判定する関数
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
                #東宮下橋を通過したら
                if entity.vehicle.trip.route_id in ["10009","10011", "10014", "10015"] and entity.vehicle.trip.direction_id == 1 and geopy_distance(35.70437416495755, 139.30905085675604, float(entity.vehicle.position.latitude),float(entity.vehicle.position.longitude)):
                # 丹木２丁目
                # if entity.vehicle.trip.route_id in ["10009","10011", "10014", "10015"] and entity.vehicle.trip.direction_id == 1 and geopy_distance(35.69544549488998, 139.3290200710432, float(entity.vehicle.position.latitude),float(entity.vehicle.position.longitude)):
                    result.append(record)

    new_df = pd.DataFrame(result, columns=column)
    new_df["timestamp"] = pd.to_datetime(new_df.timestamp, unit='s', utc=True).dt.tz_convert('Asia/Tokyo')  # タイムスタンプ情報をUNIX時間から日本時間に変換
    new_df["timestamp"] = new_df["timestamp"].dt.tz_localize(None)  # Timezone情報を削除
    return new_df 

configuration = Configuration(access_token='PGMR39IHI36Pm8i4BM1lfhXOvGBJ0NFQ6plSNwLh3PiRw7rk4loK7E4Cikh9VZARN8fWg3r1QNQhRdK91nMWTOeFzWv556B4d9CC4GrdzQbFGGeBXPVIxNVBvo5G0v55Ynq+hQ1ET5oDZsSMfBQ1eQdB04t89/1O/w1cDnyilFU=')
handler = WebhookHandler('7833d6415f2cc086223242538717bcd2')

# @app.route("/")
# def hello_world():
#     return "Hello World!"

@app.route("/", methods=['POST'])
def callback():
    # get X-Line-Signature header value
    signature = request.headers['X-Line-Signature']

    # get request body as text
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    # handle webhook body
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        app.logger.info("Invalid signature. Please check your channel access token/channel secret.")
        abort(400)

    return 'OK'


@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        
        if event.message.text == "下校":
            school_DP = datetime.now(pytz.timezone('Asia/Tokyo'))
            isweekday = isBizDay(school_DP)
            day = "平日" if isweekday == 0 else "休日"
            kasuga_AR = school_DP + timedelta(minutes=10)
            kasuga_DP = nexttrain(kasuga_AR.time(), kasugaeki, isweekday)[0]
            shinjukunishiguchi_AR = kasuga_DP + timedelta(minutes=14)
            keioshinjuku_AR = shinjukunishiguchi_AR + timedelta(minutes=6)
            keioshinjuku_DP = nexttrain(shinjukunishiguchi_AR,keiosinjukustation, isweekday)
            
            line_bot_api.reply_message_with_http_info(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=f"下校開始{school_DP.strftime('%m月%d日%H:%M')}{day}です\n"
                                        f"{kasuga_AR.strftime('%H:%M')}春日駅着\n"
                                        f"{kasuga_DP.strftime('%H:%M')}春日駅出\n"
                                        f"{shinjukunishiguchi_AR.strftime('%H:%M')}新宿西口着\n"
                                        f"{keioshinjuku_AR.strftime('%H:%M')}京王新宿着\n"
                                        f"京王新宿駅出\n"
                                        f"{keioshinjuku_DP[0].strftime('%H:%M')}\n"  
                                        f"{keioshinjuku_DP[1].strftime('%H:%M')}\n"
                                        f"{keioshinjuku_DP[2].strftime('%H:%M')}")]
                )
            )
        else:
            user_message = event.message.text
            try:
                buss_time = datetime.strptime(user_message, '%H:%M').time()
            except ValueError:
                line_bot_api.reply_message_with_http_info(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text="時刻はHH:MM形式で入力してください。")]
                    )
                )
                return
            hour, minute = buss_time.hour, buss_time.minute

            #user_message = 00:00
            buss_time = datetime.combine(datetime.today(), buss_time)
            buss_time = pytz.timezone('Asia/Tokyo').localize(buss_time)
            now_time = datetime.now(pytz.timezone('Asia/Tokyo'))
            if minute not in kasumisyougakkou[isBizDay(buss_time)][hour]:
                line_bot_api.reply_message_with_http_info(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text="その時刻にはバスはありません")]
                    )
                )
                return
            #バスが加住小学校を過ぎていたら
            # if now_time > buss_time:
            #     line_bot_api.reply_message_with_http_info(
            #         ReplyMessageRequest(
            #             reply_token=event.reply_token,
            #             messages=[TextMessage(text=f"バスはすでに加住小学校を出発しています")]))
                return 
            
            line_bot_api.reply_message_with_http_info(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=f"加住小学校を{buss_time.strftime('%H:%M')}に出発するバスを追跡しています")]
                )
            )

            # buss_timeの5分前
            start_time = buss_time - timedelta(minutes=5)
            # start_time = buss_time - timedelta(minutes=22)
            df = None
            # 5分前になるまで待機
            while now_time < start_time:
                time_module.sleep(3)
                now_time = datetime.now(pytz.timezone('Asia/Tokyo'))
            #5分前通知    
            user_id = event.source.user_id  # ユーザーIDを取得
            line_bot_api.push_message(
                {
                    "to": user_id,
                    "messages": [
                        TextMessage(
                            text="五分前になりました。"
                        )
                    ]
                }
            )
            
            #buss_timeの五分前から実行
            while df is None or df.empty:
                df = get_gtfs_rt()
                if df is not None and not df.empty:
                    line_bot_api.push_message(
                        {
                            "to": user_id,
                            "messages": [
                                TextMessage(
                                    text=f"バスが{df.iloc[0]['timestamp']}東宮下を通過しました。"
                                )
                            ]
                        }
                    )
                    return 
                else:
                    time_module.sleep(3)
                
                
        # else:
        #     line_bot_api.reply_message_with_http_info(
        #         ReplyMessageRequest(
        #             reply_token=event.reply_token,
        #             messages=[TextMessage(text=f"あなたは{event.message.text}といいました")]
        #         )
        #     )

if __name__ == "__main__":
    app.run()