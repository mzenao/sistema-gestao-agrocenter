from flask import Flask, jsonify, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date, timezone
from collections import defaultdict
from collections import OrderedDict
from sqlalchemy import extract, func
from flask_migrate import Migrate
from zoneinfo import ZoneInfo
import os

# ---------------------
# CONFIGURAÇÕES
# ---------------------
app = Flask(__name__)

# Usa a SECRET_KEY vinda das variáveis de ambiente do Railway
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY", "chave_secreta_super_secreta")

# Configuração do banco: pega a URL do Railway
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL")

# Desativa rastreamento extra
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Cria a instância do banco UMA vez
db = SQLAlchemy(app)

# Configura migrations
migrate = Migrate(app, db)

# Se quiser criar tabelas automaticamente
with app.app_context():
    db.create_all()

# ---------------------
# MODELOS
# ---------------------
class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    usuario = db.Column(db.String(100), unique=True, nullable=False)
    senha = db.Column(db.String(100), nullable=False)
    data_cadastro = db.Column(db.DateTime, default=datetime.now)


class Categoria(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), unique=True, nullable=False)


class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    preco_compra = db.Column(db.Float, nullable=False)
    preco_venda = db.Column(db.Float, nullable=False)
    margem_lucro = db.Column(db.Float)
    data_cadastro = db.Column(db.DateTime, default=datetime.now)
    categoria_id = db.Column(db.Integer, db.ForeignKey('categoria.id'))
    categoria = db.relationship('Categoria', backref='itens')


class Venda(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    forma_pagamento = db.Column(db.String(50), nullable=False)
    data_venda = db.Column(db.DateTime, default=datetime.now)
    valor_total = db.Column(db.Float, nullable=False)
    lucro_total = db.Column(db.Float, nullable=False)
    conferido = db.Column(db.Boolean, default=False, nullable=False)
    itens = db.relationship("VendaItem", backref="venda", cascade="all, delete-orphan")


class VendaItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    venda_id = db.Column(db.Integer, db.ForeignKey("venda.id"), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey("item.id"), nullable=False)
    item = db.relationship("Item")
    quantidade = db.Column(db.Integer, nullable=False, default=1)
    valor_venda = db.Column(db.Float, nullable=False)
    desconto = db.Column(db.Float, default=0)
    acrescimo = db.Column(db.Float, default=0)
    lucro = db.Column(db.Float, nullable=False)


class Despesa(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    descricao = db.Column(db.String(150), nullable=False)
    valor = db.Column(db.Float, nullable=False)
    data_despesa = db.Column(db.DateTime, default=datetime.now)
    categoria = db.Column(db.String(50), nullable=False)


# ---------------------
# ROTAS
# ---------------------

#rota para importar dados json

@app.route("/dados/pagamentos/<int:mes>")
def dados_pagamentos(mes):
    resultados = (
        db.session.query(Venda.forma_pagamento, func.sum(Venda.valor_total))
        .filter(extract('month', Venda.data_venda) == mes)
        .group_by(Venda.forma_pagamento)
        .all()
    )
    dados = [{"forma_pagamento": r[0], "total": float(r[1])} for r in resultados]
    return jsonify(dados)

@app.route("/dados/categorias/<int:mes>")
def dados_categorias(mes):
    resultados = (
        db.session.query(Categoria.nome, func.sum(VendaItem.quantidade))
        .join(Item, Item.categoria_id == Categoria.id)
        .join(VendaItem, VendaItem.item_id == Item.id)
        .join(Venda, Venda.id == VendaItem.venda_id)
        .filter(extract('month', Venda.data_venda) == mes)
        .group_by(Categoria.nome)
        .all()
    )
    dados = [{"categoria": r[0], "quantidade": int(r[1])} for r in resultados]
    return jsonify(dados)

@app.route("/dados/top-itens/<int:mes>")
def dados_top_itens(mes):
    resultados = (
        db.session.query(Item.nome, func.sum(VendaItem.quantidade))
        .join(VendaItem, VendaItem.item_id == Item.id)
        .join(Venda, Venda.id == VendaItem.venda_id)
        .filter(extract('month', Venda.data_venda) == mes)
        .group_by(Item.nome)
        .order_by(func.sum(VendaItem.quantidade).desc())
        .limit(10)
        .all()
    )
    dados = [{"item": r[0], "quantidade": int(r[1])} for r in resultados]
    return jsonify(dados)

@app.route("/dados/medias/<int:mes>")
def dados_medias(mes):
    resultados = (
        db.session.query(func.day(Venda.data_venda), func.avg(Venda.valor_total))
        .filter(extract('month', Venda.data_venda) == mes)
        .group_by(func.day(Venda.data_venda))
        .all()
    )
    dados = [{"dia": int(r[0]), "media_vendas": float(r[1])} for r in resultados]
    return jsonify(dados)


#rotas principais da aplicação

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if "usuario_id" in session:
        return redirect(url_for("dashboard"))
    else:
        if request.method == "POST":
            usuario_form = request.form['usuario']
            senha = request.form['senha']
            usuario = Usuario.query.filter_by(usuario=usuario_form).first()
            if usuario and usuario.senha == senha:
                session['usuario_id'] = usuario.id
                return redirect(url_for("dashboard"))
            else:
                # Renderiza a mesma página com flag de erro
                return render_template("login.html", erro=True)
        return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop('usuario_id', None)
    return redirect(url_for("login"))

@app.route("/dashboard")
def dashboard():
    if "usuario_id" not in session:
        return redirect(url_for("login"))
    
    # Dados do dia anterior
    from datetime import timedelta
    ontem = datetime.now().date() - timedelta(days=1)
    inicio = datetime.combine(ontem, datetime.min.time())
    fim = datetime.combine(ontem, datetime.max.time())
    
    vendas_ontem = Venda.query.filter(
        Venda.data_venda >= inicio,
        Venda.data_venda <= fim
    ).all()
    
    total_vendido = sum(v.valor_total for v in vendas_ontem)
    total_lucro = sum(v.lucro_total for v in vendas_ontem)
    quantidade_vendas = len(vendas_ontem)
    
    # Formas de pagamento
    pagamentos_por_forma = {}
    for v in vendas_ontem:
        if v.forma_pagamento not in pagamentos_por_forma:
            pagamentos_por_forma[v.forma_pagamento] = 0
        pagamentos_por_forma[v.forma_pagamento] += v.valor_total
    
    # Vendas por hora
    vendas_por_hora = {}
    for v in vendas_ontem:
        hora = v.data_venda.hour
        if hora not in vendas_por_hora:
            vendas_por_hora[hora] = 0
        vendas_por_hora[hora] += 1
    
    # Converter para lista de tuplas ordenadas
    vendas_por_hora_lista = sorted(vendas_por_hora.items())
    
    return render_template(
        "dashboard.html",
        total_vendido=total_vendido,
        total_lucro=total_lucro,
        quantidade_vendas=quantidade_vendas,
        pagamentos_por_forma=pagamentos_por_forma,
        vendas_por_hora=vendas_por_hora_lista,
        data_hoje=ontem.strftime("%d/%m/%Y")
    )

@app.route("/dados/dashboard/<data>")
def dados_dashboard(data):
    try:
        data_sel = datetime.strptime(data, "%Y-%m-%d").date()
    except ValueError:
        return jsonify({"erro": "Data inválida"}), 400
    
    inicio = datetime.combine(data_sel, datetime.min.time())
    fim = datetime.combine(data_sel, datetime.max.time())
    
    vendas = Venda.query.filter(
        Venda.data_venda >= inicio,
        Venda.data_venda <= fim
    ).all()
    
    total_vendido = sum(v.valor_total for v in vendas)
    total_lucro = sum(v.lucro_total for v in vendas)
    quantidade_vendas = len(vendas)
    
    # Formas de pagamento
    pagamentos_por_forma = {}
    for v in vendas:
        if v.forma_pagamento not in pagamentos_por_forma:
            pagamentos_por_forma[v.forma_pagamento] = 0
        pagamentos_por_forma[v.forma_pagamento] += v.valor_total
    
    # Vendas por hora
    vendas_por_hora = {}
    for v in vendas:
        hora = v.data_venda.hour
        if hora not in vendas_por_hora:
            vendas_por_hora[hora] = 0
        vendas_por_hora[hora] += 1
    
    # Ordenar horas
    vendas_por_hora_ordenado = OrderedDict(sorted(vendas_por_hora.items()))
    
    return jsonify({
        "total_vendido": round(total_vendido, 2),
        "total_lucro": round(total_lucro, 2),
        "quantidade_vendas": quantidade_vendas,
        "ticket_medio": round(total_vendido / quantidade_vendas, 2) if quantidade_vendas > 0 else 0,
        "pagamentos_por_forma": pagamentos_por_forma,
        "vendas_por_hora": vendas_por_hora_ordenado,
        "data": data_sel.strftime("%d/%m/%Y")
    })

@app.route("/vendas", methods=["GET"])
def vendas():
    if "usuario_id" not in session:
        return redirect(url_for("login"))

    tz_br = ZoneInfo("America/Sao_Paulo")

    data_str = request.args.get("data")

    try:
        data_sel = (
            datetime.strptime(data_str, "%d/%m/%Y").date()
            if data_str
            else datetime.now(tz_br).date()
        )
    except ValueError:
        data_sel = datetime.now(tz_br).date()

    inicio = datetime.combine(
        data_sel,
        datetime.min.time(),
        tzinfo=tz_br
    )

    fim = datetime.combine(
        data_sel,
        datetime.max.time(),
        tzinfo=tz_br
    )

    inicio_utc = inicio.astimezone(timezone.utc)
    fim_utc = fim.astimezone(timezone.utc)

    # vendas do dia (UTC)
    vendas = Venda.query.filter(
        Venda.data_venda >= inicio_utc,
        Venda.data_venda <= fim_utc
    ).order_by(Venda.data_venda.asc()).all()

    # converte data das vendas para Brasília
    for v in vendas:
        v.data_venda_br = v.data_venda.astimezone(tz_br)

    # itens disponíveis
    itens = Item.query.order_by(Item.nome.asc()).all()

    # carrinho da sessão
    carrinho = session.get("carrinho", [])
    total_carrinho = sum(i["valor_venda"] for i in carrinho)

    # calcula total diário
    total_diario = 0
    for v in vendas:
        for vi in v.itens:
            total_diario += (vi.valor_venda - vi.desconto + vi.acrescimo)

    # lista serializável de itens
    itens_json = [
        {"nome": i.nome, "preco_venda": i.preco_venda}
        for i in itens
    ]

    # 🔹 retorno único
    return render_template(
        "vendas.html",
        data_sel=data_sel.strftime("%d/%m/%Y"),
        vendas=vendas,
        itens=itens,
        itens_json=itens_json,
        carrinho=carrinho,
        total_carrinho=total_carrinho,
        total_diario=total_diario
    )


@app.route("/carrinho/adicionar", methods=["POST"])
def adicionar_item():
    item_nome = (request.form.get("item_nome") or "").strip()
    qtd_raw = (request.form.get("quantidade") or "").strip()
    valor_raw = (request.form.get("valor") or "").strip()
    desconto = float(request.form.get("desconto") or 0)
    acrescimo = float(request.form.get("acrescimo") or 0)

    item = Item.query.filter_by(nome=item_nome).first()
    if not item:
        flash("Item não encontrado.", "danger")
        return redirect(url_for("vendas"))

    preco_unitario = item.preco_venda

    # Se quantidade foi informada, usa ela
    if qtd_raw:
        quantidade = float(qtd_raw)
        valor_venda = (preco_unitario * quantidade) - desconto + acrescimo
    # Se não, mas valor foi informado, calcula quantidade
    elif valor_raw:
        valor_informado = float(valor_raw)
        quantidade = valor_informado / preco_unitario
        valor_venda = valor_informado - desconto + acrescimo
    else:
        # Default: 1 unidade
        quantidade = 1
        valor_venda = preco_unitario - desconto + acrescimo

    lucro = (preco_unitario - item.preco_compra) * quantidade - desconto + acrescimo

    carrinho = session.get("carrinho", [])
    carrinho.append({
        "item_id": item.id,
        "item_nome": item.nome,
        "quantidade": quantidade,
        "valor_venda": valor_venda,
        "desconto": desconto,
        "acrescimo": acrescimo,
        "lucro": lucro
    })
    session["carrinho"] = carrinho

    flash("Item adicionado ao carrinho.", "success")
    data = request.form.get("data") or request.args.get("data")
    return redirect(url_for("vendas", data=data))



@app.route("/carrinho/finalizar", methods=["POST"])
def concluir_venda():
    tz_br = ZoneInfo("America/Sao_Paulo")

    forma_pagamento = request.form.get("forma_pagamento", "dinheiro")
    data_str = request.form.get("data_venda")  # ← agora existe
    carrinho = session.get("carrinho", [])

    if not carrinho:
        flash("Carrinho vazio.", "danger")
        return redirect(url_for("vendas"))

    # 📅 define a data da venda
    if data_str:
        data_base = datetime.strptime(data_str, "%d/%m/%Y").date()
        hora_atual = datetime.now(tz_br).time()

        data_venda_br = datetime.combine(
            data_base,
            hora_atual,
            tzinfo=tz_br
        )
    else:
        data_venda_br = datetime.now(tz_br)

    # 🔐 bloqueia datas futuras
    if data_venda_br > datetime.now(tz_br):
        flash("Data da venda inválida.", "danger")
        return redirect(url_for("vendas"))

    valor_total = sum(i["valor_venda"] for i in carrinho)
    lucro_total = sum(i["lucro"] for i in carrinho)

    venda = Venda(
        forma_pagamento=forma_pagamento,
        valor_total=valor_total,
        lucro_total=lucro_total,
        data_venda=data_venda_br.astimezone(timezone.utc)  # ✅ correto
    )

    db.session.add(venda)
    db.session.flush()

    for i in carrinho:
        vi = VendaItem(
            venda_id=venda.id,
            item_id=i["item_id"],
            quantidade=i["quantidade"],
            valor_venda=i["valor_venda"],
            desconto=i["desconto"],
            acrescimo=i["acrescimo"],
            lucro=i["lucro"]
        )
        db.session.add(vi)

    db.session.commit()
    session.pop("carrinho", None)

    flash("Venda concluída!", "success")
    return redirect(url_for("vendas", data=data_str))

@app.route("/cancelar_venda", methods=["POST"])
def cancelar_venda():
    venda_id = request.form.get("venda_id")
    venda = Venda.query.get(venda_id)

    if not venda:
        flash("Venda não encontrada.", "danger")
        return redirect(url_for("vendas"))

    # Exemplo: remover a venda
    db.session.delete(venda)
    db.session.commit()

    flash("Venda cancelada com sucesso.", "success")
    return redirect(url_for("vendas"))

@app.route("/editar_venda", methods=["POST"])
def editar_venda():
    venda_id = request.form.get("venda_id")
    venda = Venda.query.get(venda_id)

    if not venda:
        flash("Venda não encontrada.", "danger")
        return redirect(url_for("vendas"))

    # Atualiza forma de pagamento
    venda.forma_pagamento = request.form.get("forma_pagamento")

    # Remove itens antigos
    VendaItem.query.filter_by(venda_id=venda.id).delete()

    # Recria itens com os novos valores
    itens = zip(
        request.form.getlist("item_nome[]"),
        request.form.getlist("quantidade[]"),
        request.form.getlist("valor[]"),
        request.form.getlist("desconto[]"),
        request.form.getlist("acrescimo[]")
    )

    valor_total = 0
    lucro_total = 0

    for nome, qtd, valor, desc, acres in itens:
        item = Item.query.filter_by(nome=nome).first()
        if item:
            quantidade = float(qtd)
            valor_venda = float(valor)
            desconto = float(desc)
            acrescimo = float(acres)
            lucro = (item.preco_venda - item.preco_compra) * quantidade - desconto + acrescimo

            vi = VendaItem(
                venda_id=venda.id,
                item_id=item.id,
                quantidade=quantidade,
                valor_venda=valor_venda,
                desconto=desconto,
                acrescimo=acrescimo,
                lucro=lucro
            )
            db.session.add(vi)
            valor_total += valor_venda
            lucro_total += lucro

    venda.valor_total = valor_total
    venda.lucro_total = lucro_total
    db.session.commit()

    flash("Venda atualizada com sucesso!", "success")
    return redirect(url_for("vendas"))

@app.route("/conferir_venda", methods=["POST"])
def conferir_venda():
    data = request.get_json()

    venda = Venda.query.get(data["id"])

    if venda:
        venda.conferido = data["conferido"]
        db.session.commit()
        return {"success": True}

    return {"success": False}, 404


@app.route("/itens", methods=["GET"])
def itens():
    if "usuario_id" not in session:
        return redirect(url_for("login"))

    q = request.args.get("q", "").strip()

    # Use contains para evitar problemas com ilike em alguns setups
    if q:
        itens = Item.query.filter(Item.nome.contains(q)).order_by(Item.nome.asc()).all()
    else:
        itens = Item.query.order_by(Item.nome.asc()).all()

    categorias = Categoria.query.all()

    pesquisando = bool(q)
    nenhum_resultado = pesquisando and len(itens) == 0

    return render_template(
        "itens.html",
        categorias=categorias,
        itens=itens,
        pesquisando=pesquisando,
        nenhum_resultado=nenhum_resultado,
        q=q
    )


@app.route("/itens", methods=["POST"])
def cadastrar_ou_editar_item():
    if "usuario_id" not in session:
        return redirect(url_for("login"))

    # Exclusão direta pela tabela (se existir)
    delete_id = request.form.get("delete_id")
    if delete_id:
        item = Item.query.get_or_404(int(delete_id))
        db.session.delete(item)
        db.session.commit()
        return redirect(url_for("itens"))

    # Cadastro/Edição
    item_id = request.form.get("item_id")
    nome = request.form.get("nome", "").strip()
    preco_compra = float(request.form.get("preco_compra", 0) or 0)
    preco_venda = float(request.form.get("preco_venda", 0) or 0)
    categoria_id = int(request.form.get("categoria_id", 0) or 0)

    margem_lucro = ((preco_venda - preco_compra) / preco_compra) * 100 if preco_compra != 0 else 0

    if item_id:
        item = Item.query.get_or_404(int(item_id))
        item.nome = nome
        item.preco_compra = preco_compra
        item.preco_venda = preco_venda
        item.margem_lucro = margem_lucro
        item.categoria_id = categoria_id
    else:
        novo_item = Item(
            nome=nome,
            preco_compra=preco_compra,
            preco_venda=preco_venda,
            margem_lucro=margem_lucro,
            categoria_id=categoria_id
        )
        db.session.add(novo_item)

    db.session.commit()
    return redirect(url_for("itens"))


@app.route("/relatorios")
def relatorios():
    if "usuario_id" not in session:
        return redirect(url_for("login"))

    from sqlalchemy import extract, func

    vendas = (
        db.session.query(
            extract('month', Venda.data_venda).label('mes'),
            func.sum(Venda.valor_total).label('valor_total')
        )
        .group_by('mes')
        .all()
    )

    pagamentos = (
        db.session.query(
            Venda.forma_pagamento,
            func.count(Venda.id).label('quantidade'),
            func.sum(Venda.valor_total).label('total')
        )
        .group_by(Venda.forma_pagamento)
        .all()
    )

    categorias = (
        db.session.query(
            Categoria.nome.label("categoria"),
            func.count(Item.id).label("quantidade")
        )
        .join(Item, Item.categoria_id == Categoria.id)
        .group_by(Categoria.nome)
        .all()
    )

    itens = (
        db.session.query(
            Item.nome.label("item"),
            func.sum(VendaItem.quantidade).label('quantidade'),
            func.sum(VendaItem.valor_venda).label('total')
        )
        .join(Item, VendaItem.item_id == Item.id)
        .group_by(Item.nome)
        .order_by(func.sum(VendaItem.quantidade).desc())
        .limit(10)
        .all()
    )

    medias = (
        db.session.query(
            extract('day', Venda.data_venda).label('dia'),
            func.avg(Venda.valor_total).label('media_vendas')
        )
        .group_by('dia')
        .all()
    )

    return render_template(
        "relatorios.html",
        vendas=vendas,
        pagamentos=pagamentos,
        categorias=categorias,
        itens=itens,
        medias=medias
    )


@app.route("/financeiro")
def financeiro():
    despesas = Despesa.query.all()
    vendas = Venda.query.all()

    # Agrupar por ano/mês
    saldos_por_ano = {}

    for v in vendas:
        ano = v.data_venda.year
        mes = v.data_venda.month
        if ano not in saldos_por_ano:
            saldos_por_ano[ano] = {}
        if mes not in saldos_por_ano[ano]:
            saldos_por_ano[ano][mes] = {"receitas": 0, "despesas": 0}
        saldos_por_ano[ano][mes]["receitas"] += v.valor_total

    for d in despesas:
        ano = d.data_despesa.year
        mes = d.data_despesa.month
        if ano not in saldos_por_ano:
            saldos_por_ano[ano] = {}
        if mes not in saldos_por_ano[ano]:
            saldos_por_ano[ano][mes] = {"receitas": 0, "despesas": 0}
        saldos_por_ano[ano][mes]["despesas"] += d.valor

    anos = sorted(saldos_por_ano.keys())

    if anos:  # ✅ só acessa se houver dados
        ano_inicial = anos[0]
        meses = [datetime(ano_inicial, m, 1).strftime("%b") for m in range(1, 13)]
        receitas_mensais = [saldos_por_ano[ano_inicial].get(m, {"receitas": 0})["receitas"] for m in range(1, 13)]
        despesas_mensais = [saldos_por_ano[ano_inicial].get(m, {"despesas": 0})["despesas"] for m in range(1, 13)]
    else:  # ✅ fallback quando não há registros
        ano_inicial = datetime.now().year
        meses = [datetime(ano_inicial, m, 1).strftime("%b") for m in range(1, 13)]
        receitas_mensais = [0 for _ in range(12)]
        despesas_mensais = [0 for _ in range(12)]

    return render_template(
        "financeiro.html",
        despesas=despesas,
        anos=anos,
        ano_inicial=ano_inicial,
        meses=meses,
        receitas_mensais=receitas_mensais,
        despesas_mensais=despesas_mensais,
        saldos_por_ano=saldos_por_ano
    )


@app.route("/financeiro/cadastrar", methods=["POST"])
def financeiro_cadastrar():
    descricao = request.form.get("descricao")
    valor = float(request.form.get("valor"))
    data_str = request.form.get("data")
    categoria = request.form.get("categoria")  # novo campo
    data = datetime.strptime(data_str, "%d/%m/%Y")
    nova = Despesa(descricao=descricao, valor=valor, data_despesa=data, categoria=categoria)
    db.session.add(nova)
    db.session.commit()

    flash("Despesa cadastrada com sucesso!", "success")
    return redirect(url_for("financeiro"))


@app.route("/financeiro/excluir", methods=["POST"])
def financeiro_excluir():
    despesa_id = request.form.get("conta_id")
    despesa = Despesa.query.get(despesa_id)
    if despesa:
        db.session.delete(despesa)
        db.session.commit()
        flash("Despesa excluída com sucesso!", "success")
    else:
        flash("Despesa não encontrada.", "danger")
    return redirect(url_for("financeiro"))


@app.route("/financeiro_dados/<int:ano>")
def financeiro_dados(ano):
    # mesma lógica de agrupamento, mas filtrando pelo ano
    despesas = Despesa.query.all()
    vendas = Venda.query.all()

    saldos_por_ano = {}

    for v in vendas:
        a = v.data_venda.year
        m = v.data_venda.month
        if a not in saldos_por_ano:
            saldos_por_ano[a] = {}
        if m not in saldos_por_ano[a]:
            saldos_por_ano[a][m] = {"receitas": 0, "despesas": 0}
        saldos_por_ano[a][m]["receitas"] += v.valor_total

    for d in despesas:
        a = d.data_despesa.year
        m = d.data_despesa.month
        if a not in saldos_por_ano:
            saldos_por_ano[a] = {}
        if m not in saldos_por_ano[a]:
            saldos_por_ano[a][m] = {"receitas": 0, "despesas": 0}
        saldos_por_ano[a][m]["despesas"] += d.valor

    meses = [datetime(ano, m, 1).strftime("%b") for m in range(1, 13)]
    receitas = [saldos_por_ano.get(ano, {}).get(m, {"receitas": 0})["receitas"] for m in range(1, 13)]
    despesas = [saldos_por_ano.get(ano, {}).get(m, {"despesas": 0})["despesas"] for m in range(1, 13)]

    return jsonify({"meses": meses, "receitas": receitas, "despesas": despesas})

# ---------------------
# MAIN
# ---------------------
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(host="0.0.0.0", port=5000, debug=True)