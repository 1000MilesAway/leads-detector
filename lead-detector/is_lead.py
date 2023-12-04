from __future__ import annotations

import logging
import pprint
import re
import requests
import openai

from math import ceil
from datetime import datetime, timedelta
import asyncio
import csv

import conf
from filter_settings import triggers_ru, prompt


class IsLead:
    PREFIX = 'IsLead'
    
    def __init__(self, openai):
        self.openai = openai

    async def validate_response(self, chat_id, message):
        if len(message)>512:
            return False, 'message to big', 0, ""
        
        first_trigger = None
        msg_lower = message.lower()
        for trigger in triggers_ru:
            if trigger.lower() in msg_lower:
                first_trigger = trigger
                break

        if first_trigger is None:
            return False, 'no trigger word found', 0, ""
        

        _conversation = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": message},
        ]
        completion = self.openai.chat.completions.create(model="gpt-3.5-turbo", messages=_conversation, max_tokens=100)
        
        text = completion.choices[0].message.content

        explain_pattern = re.compile(r'EXPLAIN: (.*?)\n')
        rate_pattern = re.compile(r'RATE: (\d)')
        status_pattern = re.compile(r'INDICATOR: (yes|Yes|no|No)', re.IGNORECASE)

        explain_match = explain_pattern.search(text)
        rate_match = rate_pattern.search(text)
        status_match = status_pattern.search(text)

        explain = explain_match.group(1) if explain_match else None
        rate = rate_match.group(1) if rate_match else None
        status = status_match.group(1) if status_match else None

        if status is None:
            if len(text.strip().split()) == 1:
                if text.strip().lower() == 'yes':
                    status = 'yes'
                elif text.strip().lower() == 'no':
                    status = 'no'

        try:
            rate = int(rate) if rate else None
        except Exception as exc:
            logging.exception(f'failed to parse {type(exc)=} {exc=}')
            rate = None

        if isinstance(status, str):
            status = status.strip().lower() == 'yes'
        else:
            status = False

        if not status:
            logging.info(f'{self.PREFIX} BAD RESPONSE FOR CONVERSATION: {pprint.pformat(_conversation)}')

        return status, explain, rate, first_trigger
    

    async def validate(self, page):
        queue = asyncio.Queue()
        
        while True:
            messages, ok = await get_chat(page)
            if ok:
                break
            
        if messages == []:
            print("End of pages")
            return
                    
        for message in messages:
            queue.put_nowait(message)
        
        
        tasks = []
        for i in range(10):
            task = asyncio.create_task(self.worker(f'worker-{i}', queue))
            tasks.append(task)
        
        
        await queue.join()
        for task in tasks:
            task.cancel()

        await asyncio.gather(*tasks, return_exceptions=True)
        print(f"Page#{page} DONE!")
        


    async def worker(self, name, queue):
        while True:
            message = await queue.get()
            
            try:
                status, explain, rate, trigger = await self.validate_response(0, message)
                if status:
                    print(f'GOOD: {explain=}')
                    print(f'GOOD: {rate=}')
                    print(f'GOOD: {message=}')
                    print(f'GOOD: {trigger=}')
                    print('====')
                    mess_result = {"message": message, "trigger": trigger, "explain": explain, "rate": rate,}
                        
                    writer.writerows([mess_result])
            except Exception as exc:
                print(f'failed to validate {type(exc)=} {exc=}')
            finally:
                queue.task_done()
        
async def run():
    client = openai.AsyncOpenAI(api_key=conf.GPT_TOKEN)
    handler = IsLead(client) 
      
    pages = ceil(get_mes_count(conf.DAYS_TO_SEARCH) / conf.PER_PAGE)
    pages = 1

    tasks = []
    for i in range(pages):
        task = asyncio.create_task(handler.validate(i))
        tasks.append(task)

    await asyncio.gather(*tasks)

async def get_chat(page, days):
    date = str((datetime.today() - timedelta(days=days)).date())
    page = f"page={page}"
    filter = f"filter=(created>'{date}')&expand=fromGroup&perPage={conf.PER_PAGE}"
    
    resp = requests.get(f"{conf.POCKETBASE_URL}/api/collections/history2/records?{page}&{filter}", headers={'token': conf.POCKETBASE_TOKEN})
    
    messages = [x["message"] for x in resp.json()["items"]]
    
    print(messages)
    print(resp.ok)
    return messages, resp.ok

def get_mes_count(days):
    date = str((datetime.today() - timedelta(days=days)).date())
    filter = f"filter=(created>'{date}')&expand=fromGroup&perPage=1"
    resp = requests.get(f"{conf.POCKETBASE_URL}/api/collections/history2/records?0&{filter}", headers={'token': conf.POCKETBASE_TOKEN})
    
    return resp.json()["totalItems"]

if __name__ == '__main__':
    fieldnames = ["message", "trigger", "explain", "rate"]
    filename = datetime.now().strftime('%y-%m-%d_%H:%M')
    file = open(f"./{filename}.csv", mode='w', newline='', encoding="utf-8")
    writer = csv.DictWriter(file, fieldnames=fieldnames)
    writer.writeheader()

    asyncio.run(run())

    file.close
    
