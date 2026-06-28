import csv, math, re, os, tempfile
from collections import Counter
from flask import Flask, request, make_response
from gtts import gTTS
import requests as req

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

def transcribe_audio(media_url, account_sid, auth_token):
    """Download voice note and transcribe with Whisper."""
    try:
        import whisper
        # Download audio from Twilio
        response = req.get(media_url, auth=(account_sid, auth_token))
        with tempfile.NamedTemporaryFile(suffix='.ogg', delete=False) as f:
            f.write(response.content)
            tmp_path = f.name
        # Transcribe
        model = whisper.load_model('small')
        result = model.transcribe(tmp_path, language='en')
        os.unlink(tmp_path)
        return result['text'].strip()
    except Exception as e:
        print(f"Transcription error: {e}")
        return None

def text_to_voice(text, filename):
    """Convert text to speech audio file."""
    try:
        tts = gTTS(text=text, lang='en', slow=False)
        tts.save(filename)
        return True
    except Exception as e:
        print(f"TTS error: {e}")
        return False

@app.route('/webhook', methods=['POST'])
def webhook():
    from twilio.twiml.messaging_response import MessagingResponse
    from twilio.rest import Client

    account_sid = os.environ.get('TWILIO_ACCOUNT_SID', '')
    auth_token = os.environ.get('TWILIO_AUTH_TOKEN', '')

    incoming_text = request.form.get('Body', '').strip()
    media_url = request.form.get('MediaUrl0', '')
    media_type = request.form.get('MediaContentType0', '')
    from_number = request.form.get('From', '')

    resp = MessagingResponse()

    # Get query — voice or text
    user_query = ''
    is_voice = False

    if media_url and 'audio' in media_type:
        is_voice = True
        print(f"Voice message received from {from_number}")
        user_query = transcribe_audio(media_url, account_sid, auth_token)
        if not user_query:
            resp.message("🙏 Sorry, could not understand the voice message. Please try again or type your question.")
            return make_response(str(resp))
        print(f"Transcribed: {user_query}")
    else:
        user_query = incoming_text

    if not user_query:
        resp.message("🙏 Namaskar! Ask any farming or health question.")
        return make_response(str(resp))

    # Search knowledge base
    match = search(user_query)
    if not match:
        resp.message("🙏 No information found. Please try a different question.")
        return make_response(str(resp))

    emoji = "🌾" if match.get('domain') == 'agriculture' else "🏥"
    answer_text = clean(match.get('response_en', '')[:400])
    reply_text = f"{emoji} {answer_text}"

    # Send voice reply if voice input
    if is_voice and account_sid and auth_token:
        try:
            audio_file = tempfile.mktemp(suffix='.mp3')
            if text_to_voice(answer_text, audio_file):
                # For voice reply we still send text (voice hosting needs extra setup)
                reply_text = f"🎤 You asked: {user_query[:50]}...\n\n{reply_text}"
        except Exception as e:
            print(f"Voice reply error: {e}")

    resp.message(reply_text)
    response = make_response(str(resp))
    response.headers['Content-Type'] = 'application/xml'
    return response

@app.route('/')
def home():
    return f"SantaliConnect Bot running! KB: {len(KB)} entries | Voice: enabled"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=False)
