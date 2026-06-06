from django.contrib import messages
from django.shortcuts import render, redirect


def about(request):
    return render(request, 'pages/about.html')


def contact(request):
    if request.method == 'POST':
        # Projeto acadêmico: não envia e-mail real, apenas confirma o recebimento.
        messages.success(request, 'Mensagem enviada! Em um cenário real, retornaríamos por e-mail.')
        return redirect('contact')
    return render(request, 'pages/contact.html')


def help_center(request):
    return render(request, 'pages/help.html')


def privacy(request):
    return render(request, 'pages/privacy.html')


def terms(request):
    return render(request, 'pages/terms.html')
