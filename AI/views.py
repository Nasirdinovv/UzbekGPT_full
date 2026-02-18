import json, requests
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.contrib import messages
from django.conf import settings
from .models import ChatSession, ChatMessage

# --- AUTH VIEWS (O'zgarishsiz qoladi) ---
def login_view(request):
    if request.user.is_authenticated: return redirect('chat')
    if request.method == 'POST':
        u, p = request.POST.get('username', '').strip(), request.POST.get('password', '')
        user = authenticate(username=u, password=p)
        if user: login(request, user); return redirect('chat')
        else: messages.error(request, 'Username yoki parol xato!')
    return render(request, 'login.html')

def register_view(request):
    if request.user.is_authenticated: return redirect('chat')
    if request.method == 'POST':
        u, p1 = request.POST.get('username', '').strip(), request.POST.get('password1', '')
        if User.objects.filter(username=u).exists(): messages.error(request, 'Username band!')
        else: User.objects.create_user(username=u, password=p1); return redirect('login')
    return render(request, 'register.html')

def logout_view(request):
    logout(request); return redirect('login')

# --- CHAT VIEWS ---
@login_required(login_url='login')
def chat_view(request):
    sessions = ChatSession.objects.filter(user=request.user)
    session_id = request.GET.get('session')
    current_session = get_object_or_404(ChatSession, id=session_id, user=request.user) if session_id else None
    return render(request, 'chat.html', {
        'sessions': sessions,
        'current_session': current_session,
        'chat_messages': current_session.messages.all() if current_session else []
    })

@login_required(login_url='login')
def new_session(request):
    session = ChatSession.objects.create(user=request.user, title="Yangi suhbat")
    return redirect(f'/chat/?session={session.id}')

@login_required(login_url='login')
def delete_session(request, session_id):
    get_object_or_404(ChatSession, id=session_id, user=request.user).delete()
    return redirect('chat')

@login_required(login_url='login')
def send_message(request):
    if request.method != 'POST': 
        return JsonResponse({'error': 'Faqat POST so\'rovlar qabul qilinadi'}, status=405)
    
    try:
        data = json.loads(request.body)
        user_message = data.get('message', '').strip()
        session_id = data.get('session_id')
        
        # 1. Sessiyani olish va foydalanuvchi xabarini saqlash
        session = get_object_or_404(ChatSession, id=session_id, user=request.user)
        ChatMessage.objects.create(session=session, role='user', content=user_message)

        # 2. Ishlatiladigan modellar ro'yxati
        models_to_try = [
            "google/gemini-flash-1.5-8b", 
            "meta-llama/llama-3.1-8b-instruct",
            "mistralai/mistral-7b-instruct:free"
        ]
        
        ai_reply = ""
        
        # 3. Modelni aylantirib so'rov yuborish
        for model_name in models_to_try:
            try:
                response = requests.post(
                    url="https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "http://127.0.0.1:8000",
                    },
                    data=json.dumps({
                        "model": model_name,
                        "messages": [
                            {
                                "role": "system", 
                                "content": "Sen O'zbekGPT-san. Sadas kompaniyasi tomonidan yaratilgansan. Savollarga aniq, mantiqiy va faqat o'zbek tilida javob ber. Matematik savollarda faqat sonli natijani ko'rsat, aljirama."
                            },
                            {"role": "user", "content": user_message}
                        ],
                        "temperature": 0.1, # Model "aljiramasligi" uchun eng muhim parametr
                        "max_tokens": 1000
                    }),
                    timeout=20
                )
                
                result = response.json()
                if 'choices' in result and len(result['choices']) > 0:
                    ai_reply = result['choices'][0]['message']['content']
                    break # Javob muvaffaqiyatli bo'lsa, sikldan chiqamiz
                else:
                    time.sleep(1) # Agar model band bo'lsa, 1 soniya kutib keyingisiga o'tadi
            except Exception as e:
                print(f"Model {model_name} xatosi: {e}")
                continue 

        if not ai_reply:
            ai_reply = "Kechirasiz, barcha modellar hozircha band. Birozdan so'ng qayta urinib ko'ring."

    except Exception as e:
        ai_reply = f"Tizimda texnik xatolik: {str(e)}"

    # 4. AI javobini bazaga saqlash va qaytarish
    ChatMessage.objects.create(session=session, role='assistant', content=ai_reply)
    return JsonResponse({'reply': ai_reply, 'session_id': session.id})  