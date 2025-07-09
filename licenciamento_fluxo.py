from flask import Flask, render_template, request, redirect, url_for, send_from_directory, session, make_response, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os
from io import BytesIO
from werkzeug.utils import secure_filename
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

app = Flask(__name__)
app.secret_key = 'segredo-super-seguro'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///licenciamento.db'
app.config['UPLOAD_FOLDER'] = 'uploads'
db = SQLAlchemy(app)

# MODELOS
class Processo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    protocolo = db.Column(db.String(100), nullable=False)
    solicitante = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(100), default='Recebido')
    data_inicio = db.Column(db.DateTime, default=datetime.utcnow)
    documentos = db.relationship('Documento', backref='processo', lazy=True)
    condicionantes = db.relationship('Condicionante', backref='processo', lazy=True)
    fiscalizacoes = db.relationship('Fiscalizacao', backref='processo', lazy=True)

class Documento(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    processo_id = db.Column(db.Integer, db.ForeignKey('processo.id'))
    tipo = db.Column(db.String(100))
    nome_arquivo = db.Column(db.String(100))
    data_envio = db.Column(db.DateTime, default=datetime.utcnow)

class Condicionante(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    processo_id = db.Column(db.Integer, db.ForeignKey('processo.id'))
    descricao = db.Column(db.String(200))
    status = db.Column(db.String(50), default='Pendente')
    data_limite = db.Column(db.DateTime)

class Fiscalizacao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    processo_id = db.Column(db.Integer, db.ForeignKey('processo.id'))
    relatorio = db.Column(db.String(200))
    data_execucao = db.Column(db.DateTime, default=datetime.utcnow)

# ROTA PRINCIPAL
@app.route('/')
def index():
    if 'setor' not in session:
        return redirect(url_for('login'))
    processos = Processo.query.all()
    return render_template('index.html', processos=processos, setor=session['setor'])

# LOGIN
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        setor = request.form['setor']
        session['setor'] = setor
        return redirect(url_for('index'))
    return render_template('login.html')

# LOGOUT
@app.route('/logout')
def logout():
    session.pop('setor', None)
    return redirect(url_for('login'))

# ROTAS MONITORAMENTO E FISCALIZAÇÃO
@app.route('/monitoramento')
def monitoramento():
    if 'setor' not in session or session['setor'].lower() != 'monitoramento':
        return redirect(url_for('login'))
    processos = Processo.query.all()
    return render_template('monitoramento.html', processos=processos)

@app.route('/condicionantes/<int:id>', methods=['GET', 'POST'])
def condicionantes(id):
    if 'setor' not in session or session['setor'].lower() != 'monitoramento':
        return redirect(url_for('login'))
    processo = Processo.query.get_or_404(id)
    if request.method == 'POST':
        descricao = request.form['descricao']
        data_limite = datetime.strptime(request.form['data_limite'], '%Y-%m-%d')
        cond = Condicionante(processo_id=id, descricao=descricao, data_limite=data_limite)
        db.session.add(cond)
        db.session.commit()
        return redirect(url_for('condicionantes', id=id))
    return render_template('condicionantes.html', processo=processo)

@app.route('/fiscalizacao')
def fiscalizacao():
    if 'setor' not in session or session['setor'].lower() != 'fiscalizacao':
        return redirect(url_for('login'))
    fiscalizacoes = Fiscalizacao.query.all()
    return render_template('fiscalizacao.html', fiscalizacoes=fiscalizacoes)

@app.route('/fiscalizar/<int:id>', methods=['POST'])
def fiscalizar(id):
    if 'setor' not in session or session['setor'].lower() != 'fiscalizacao':
        return redirect(url_for('login'))
    relatorio = request.form['relatorio']
    fiscal = Fiscalizacao(processo_id=id, relatorio=relatorio)
    db.session.add(fiscal)
    db.session.commit()
    return redirect(url_for('fiscalizacao'))

# TELA DETALHADA DO PROCESSO
@app.route('/processo/<int:id>', methods=['GET', 'POST'])
def detalhar_processo(id):
    if 'setor' not in session:
        return redirect(url_for('login'))
    processo = Processo.query.get_or_404(id)
    if request.method == 'POST':
        if 'descricao_cond' in request.form:
            descricao = request.form['descricao_cond']
            data_limite = datetime.strptime(request.form['data_limite'], '%Y-%m-%d')
            nova = Condicionante(processo_id=id, descricao=descricao, data_limite=data_limite)
            db.session.add(nova)
        elif 'tipo_doc' in request.form:
            tipo = request.form['tipo_doc']
            arquivo = request.files['arquivo_doc']
            if arquivo:
                filename = secure_filename(arquivo.filename)
                caminho = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                arquivo.save(caminho)
                doc = Documento(processo_id=id, tipo=tipo, nome_arquivo=filename)
                db.session.add(doc)
        elif 'relatorio_fisc' in request.form:
            relatorio = request.form['relatorio_fisc']
            fisc = Fiscalizacao(processo_id=id, relatorio=relatorio)
            db.session.add(fisc)
        db.session.commit()
        return redirect(url_for('detalhar_processo', id=id))
    return render_template('detalhado.html', processo=processo)

# EXPORTAR RELATÓRIO EM PDF
@app.route('/pdf/<int:id>')
def gerar_pdf(id):
    if 'setor' not in session:
        return redirect(url_for('login'))
    processo = Processo.query.get_or_404(id)
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    p.setFont("Helvetica", 12)
    y = 800
    p.drawString(100, y, f"Relatório do Processo #{processo.id}")
    y -= 30
    p.drawString(100, y, f"Protocolo: {processo.protocolo}")
    y -= 20
    p.drawString(100, y, f"Solicitante: {processo.solicitante}")
    y -= 20
    p.drawString(100, y, f"Status: {processo.status}")
    y -= 40
    p.drawString(100, y, "Documentos:")
    for doc in processo.documentos:
        y -= 20
        p.drawString(120, y, f"- {doc.tipo}: {doc.nome_arquivo}")
    y -= 30
    p.drawString(100, y, "Condicionantes:")
    for cond in processo.condicionantes:
        y -= 20
        p.drawString(120, y, f"- {cond.descricao} ({cond.status})")
    y -= 30
    p.drawString(100, y, "Fiscalizações:")
    for fisc in processo.fiscalizacoes:
        y -= 20
        p.drawString(120, y, f"- {fisc.relatorio} em {fisc.data_execucao.strftime('%d/%m/%Y')}")
    p.showPage()
    p.save()
    buffer.seek(0)
    response = make_response(buffer.read())
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename=processo_{processo.id}.pdf'
    return response

# UPLOAD DE DOCUMENTOS
@app.route('/upload/<int:id>', methods=['GET', 'POST'])
def upload(id):
    if 'setor' not in session:
        return redirect(url_for('login'))
    processo = Processo.query.get_or_404(id)
    if request.method == 'POST':
        tipo = request.form['tipo']
        arquivo = request.files['arquivo']
        if arquivo:
            filename = secure_filename(arquivo.filename)
            caminho = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            arquivo.save(caminho)
            doc = Documento(processo_id=id, tipo=tipo, nome_arquivo=filename)
            db.session.add(doc)
            db.session.commit()
            flash('Documento enviado com sucesso!')
            return redirect(url_for('upload', id=id))
    return render_template('upload.html', processo=processo)

@app.route('/visualizar/<nome_arquivo>')
def visualizar_documento(nome_arquivo):
    if 'setor' not in session:
        return redirect(url_for('login'))
    return send_from_directory(app.config['UPLOAD_FOLDER'], nome_arquivo)

# CRIAR DB E PASTAS NECESSÁRIAS
if __name__ == '__main__':
    if not os.path.exists('uploads'):
        os.makedirs('uploads')
    if not os.path.exists('templates'):
        os.makedirs('templates')
    with app.app_context():
        db.create_all()
    app.run(debug=True)
