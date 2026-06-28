import csv, math, re, os
from collections import Counter
from flask import Flask, request,make_response

app = Flask(__name__)
KB = []

def load_kb():
    global KB
    path = 'jharkhand_agri_health_qa.csv'
    if not os.path.exists(path):
        print("CSV not found!")
        return
    with open(path, encoding='utf-8') as f:
        KB = list(csv.DictReader(f))
    print(f"Loaded {len(KB)} entries")

load_kb()
df = Counter()
for r in KB:
    for t in set(r.get('instruction_en','').lower().split()):
        df[t] += 1
IDF = {t: math.log((len(KB)+1)/(c+1)) for t,c in df.items()}

def search(query):
    if not KB:
        return None
    def score(r):
        doc = r.get('instruction_en','').lower().split()
        tf = Counter(doc)
        n = len(doc)+1
        return sum((tf.get(w,0)/n)*IDF.get(w,0) for w in query.lower().split())
    return sorted(KB, key=score, reverse=True)[0]

def clean(text):
    text = re.sub(r',+', ',', text or '')
    text = re.sub(r'\s+', ' ', text).strip()
    if text and text[-1] not in '.!?':
        text += '.'
    return text[0].upper() + text[1:] if text else text

@app.route('/webhook', methods=['POST'])
def webhook():
    from twilio.twiml.messaging_response import MessagingResponse
    msg = request.form.get('Body','').strip()
    m = search(msg)
    if m:
        emoji = "" if m.get('domain')=='agriculture' else ""
        reply = f"{emoji} {clean(m.get('response_en','')[:400])}"
    else:
        reply = " Namaskar! Ask about farming or health in Jharkhand."
    r = MessagingResponse()
    r.message(reply)
    response =make_response(str(r))
    response.headers['content-type'] = 'application/xml'
    return response

@app.route('/')
def home():
    return f"SantaliConnect Bot running! KB: {len(KB)} entries"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)