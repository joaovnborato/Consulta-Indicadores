from flask import Flask, render_template, request, redirect, session, url_for
import pymssql
import os

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'chave-padrao-fraca')

def conectar_banco():
    try:
        conn_str = os.getenv('DATABASE_URL')
        server, user, password, database = conn_str.split(';')
        conexao = pymssql.connect(
            server=server,
            user=user,
            password=password,
            database=database
        )    
        return conexao
    except Exception as e:
        print("Erro ao conectar:", e)
        return None

@app.route('/', methods=['GET', 'POST'])
def login():
    mensagem = ''
    if request.method == 'POST':
        id_motorista = request.form['id_motorista']
        senha = request.form['cpf']

        conexao = conectar_banco()
        if conexao:
            cursor = conexao.cursor(as_dict=True)
            cursor.execute("SELECT * FROM Motoristas WHERE ID_Motorista = %s AND CPF = %s", (id_motorista, senha))
            motorista = cursor.fetchone()
            cursor.close()
            conexao.close()

            if motorista:
                session['id_motorista'] = id_motorista

                # Verifica se o ID é de supervisor
                if id_motorista.upper() in ['001', '002']:
                    return redirect(url_for('painel_supervisor'))
                else:
                    return redirect(url_for('painel'))

            else:
                mensagem = 'ID ou Senha incorretos.'

    return render_template('login.html', mensagem=mensagem)


def calcular_media(lista, chave, ignora_percentual=False):
    valores = []
    for item in lista:
        valor = item[chave]
        if not valor or valor == "-":
            continue
        if ignora_percentual:
            valor = str(valor).replace("%", "").strip().replace(",", ".")
        try:
            valor_float = float(valor)
            valores.append(valor_float)
        except ValueError:
            continue
    if not valores:
        return "-"
    media = sum(valores) / len(valores)
    return round(media, 2)

@app.route('/painel')
def painel():
    if 'id_motorista' not in session:
        return redirect(url_for('login'))

    id_motorista = session['id_motorista']
    conexao = conectar_banco()
    dados_formatados = []
    observacoes = []

    if conexao:
        cursor = conexao.cursor(as_dict=True)
        try:
            # Buscar indicadores
            cursor.execute("""
                SELECT 
                    CONVERT(varchar, D.Data, 23) AS DataISO, 
                    D.Devolucao_Porcentagem, 
                    ISNULL(S.Dispersao_KM, 0) AS Dispersao_KM,
                    R.Rating,
                    ISNULL(P.Reposicao_Valor, 0) AS Reposicao_Valor,
                    ISNULL(F.Refugo_Porcentagem, 0) AS Refugo_Porcentagem
                FROM Devolucao D
                LEFT JOIN Dispersao S ON D.ID_Motorista = S.ID_Motorista AND D.Data = S.Data
                LEFT JOIN Rating R ON D.ID_Motorista = R.ID_Motorista AND D.Data = R.Data
                LEFT JOIN Reposicao P ON D.ID_Motorista = P.ID_Motorista AND D.Data = P.Data
                LEFT JOIN Refugo F ON D.ID_Motorista = F.ID_Motorista AND D.Data = F.Data
                WHERE D.ID_Motorista = %s
                ORDER BY D.Data ASC
            """, (id_motorista,))
            
            resultados = cursor.fetchall()

            for linha in resultados:
                data = linha['DataISO']
                if data:
                    partes = data.split('-')
                    data_formatada = f"{partes[2]}-{partes[1]}-{partes[0]}"
                else:
                    data_formatada = "-"

                devolucao_porcentagem_valor = linha['Devolucao_Porcentagem']
                if devolucao_porcentagem_valor is not None:
                    devolucao_porcentagem_valor = str(devolucao_porcentagem_valor).replace("%", "").strip()
                else:
                    devolucao_porcentagem_valor = "-"


                if devolucao_porcentagem_valor == "-" or devolucao_porcentagem_valor == "" or devolucao_porcentagem_valor is None:
                    dispersao = "-"
                    reposicao = "-"
                    refugo = "-"
                else:
                    dispersao = linha['Dispersao_KM'] if linha['Dispersao_KM'] is not None else 0
                    reposicao = linha['Reposicao_Valor'] if linha['Reposicao_Valor'] is not None else 0
                    refugo = linha['Refugo_Porcentagem'] if linha['Refugo_Porcentagem'] is not None else 0

                # Rating sempre entra, independente da Devolução
                rating = linha['Rating'] if linha['Rating'] is not None else "-"

                dados_formatados.append({
                    'Data': data_formatada,
                    'Devolucao_Porcentagem': devolucao_porcentagem_valor,
                    'Dispersao_KM': dispersao,
                    'Rating': rating.replace(',00', ''),
                    'Reposicao_Valor': reposicao.replace('.', ','),
                    'Refugo_Porcentagem': refugo
                })


            # Buscar observações
            cursor.execute("SELECT Texto FROM Observacoes WHERE ID_Motorista = %s", (id_motorista,))
            observacoes = [linha['Texto'] for linha in cursor.fetchall()]

        except Exception as e:
            print("Erro ao consultar o banco:", e)
        finally:
            cursor.close()
            conexao.close()

    media_devolucao_porcentagem = calcular_media(dados_formatados, 'Devolucao_Porcentagem', ignora_percentual=True)
    media_dispersao_km = calcular_media(dados_formatados, 'Dispersao_KM', ignora_percentual=True)
    media_rating = calcular_media(dados_formatados, 'Rating')
    soma_reposicao = sum(
        float(item['Reposicao_Valor'].replace(',', '.')) 
        for item in dados_formatados 
        if item['Reposicao_Valor'] not in (None, '', 'N/A', '-')
    )
    media_refugo = calcular_media(dados_formatados, 'Refugo_Porcentagem', ignora_percentual=True)

    return render_template('painel.html', dados=dados_formatados, observacoes=observacoes,
                       medias={
                           'Devolucao_Porcentagem': media_devolucao_porcentagem,
                           'Dispersao_KM': media_dispersao_km,
                           'Rating': media_rating,
                           'Reposicao_Valor': f"{soma_reposicao:.2f}".replace('.', ','),
                           'Refugo_Porcentagem': media_refugo
})


@app.route('/painel_supervisor', methods=['GET', 'POST'])
def painel_supervisor():
    conexao = conectar_banco()
    funcionarios = []
    dados_formatados = []
    indicadores = None
    mensagem = ''

    if conexao:
        cursor = conexao.cursor(as_dict=True)

        # Buscar lista de motoristas para o select
        cursor.execute("""
            SELECT DISTINCT M.ID_Motorista, M.Nome_Completo
            FROM Motoristas M
            WHERE M.ID_Motorista IN (
                SELECT ID_Motorista FROM Devolucao
                UNION
                SELECT ID_Motorista FROM Dispersao
                UNION
                SELECT ID_Motorista FROM Rating
                UNION
                SELECT ID_Motorista FROM Reposicao
                UNION
                SELECT ID_Motorista FROM Refugo
            )
            ORDER BY M.Nome_Completo
        """)

        funcionarios = cursor.fetchall()

        # Se o supervisor escolheu um motorista para visualizar indicadores
        if request.method == 'POST':
            id_selecionado = request.form.get('id_motorista_selecionado')

            # Buscar indicadores do motorista selecionado
            cursor.execute("""
                SELECT 
                    CONVERT(varchar, D.Data, 23) AS DataISO, 
                    D.Devolucao_Porcentagem, 
                    ISNULL(S.Dispersao_KM, 0) AS Dispersao_KM,
                    R.Rating,
                    ISNULL(P.Reposicao_Valor, 0) AS Reposicao_Valor,
                    ISNULL(F.Refugo_Porcentagem, 0) AS Refugo_Porcentagem
                FROM Devolucao D
                LEFT JOIN Dispersao S ON D.ID_Motorista = S.ID_Motorista AND D.Data = S.Data
                LEFT JOIN Rating R ON D.ID_Motorista = R.ID_Motorista AND D.Data = R.Data
                LEFT JOIN Reposicao P ON D.ID_Motorista = P.ID_Motorista AND D.Data = P.Data
                LEFT JOIN Refugo F ON D.ID_Motorista = F.ID_Motorista AND D.Data = F.Data
                WHERE D.ID_Motorista = %s
                ORDER BY D.Data ASC
            """, (id_selecionado,))
            
            resultados = cursor.fetchall()

            for linha in resultados:
                data = linha['DataISO']
                if data:
                    partes = data.split('-')
                    data_formatada = f"{partes[2]}-{partes[1]}-{partes[0]}"
                else:
                    data_formatada = "-"

                devolucao_porcentagem_valor = linha['Devolucao_Porcentagem']
                if devolucao_porcentagem_valor is None or devolucao_porcentagem_valor == "":
                    devolucao_porcentagem_valor = "-"

                if devolucao_porcentagem_valor == "-" or devolucao_porcentagem_valor == "" or devolucao_porcentagem_valor is None:
                    dispersao = "-"
                    reposicao = "-"
                    refugo = "-"
                else:
                    dispersao = linha['Dispersao_KM'] if linha['Dispersao_KM'] is not None else 0
                    reposicao = linha['Reposicao_Valor'] if linha['Reposicao_Valor'] is not None else 0
                    refugo = linha['Refugo_Porcentagem'] if linha['Refugo_Porcentagem'] is not None else 0

                # Rating sempre entra, independente da Devolução
                rating = linha['Rating'] if linha['Rating'] is not None else "-"

                dados_formatados.append({
                    'Data': data_formatada,
                    'Devolucao_Porcentagem': devolucao_porcentagem_valor,
                    'Dispersao_KM': dispersao,
                    'Rating': rating.replace(',00', ''),
                    'Reposicao_Valor': reposicao.replace('.', ','),
                    'Refugo_Porcentagem': refugo
                })


        cursor.close()
        conexao.close()

    indicadores = dados_formatados
        # Calcular médias
    media_devolucao_porcentagem = calcular_media(dados_formatados, 'Devolucao_Porcentagem', ignora_percentual=True)
    media_dispersao_km = calcular_media(dados_formatados, 'Dispersao_KM', ignora_percentual=True)
    media_rating = calcular_media(dados_formatados, 'Rating')
    soma_reposicao = sum(
        float(item['Reposicao_Valor'].replace(',', '.')) 
        for item in dados_formatados 
        if item['Reposicao_Valor'] not in (None, '', 'N/A', '-')
    )

    media_refugo = calcular_media(dados_formatados, 'Refugo_Porcentagem', ignora_percentual=True)

    medias = {
        'Devolucao_Porcentagem': media_devolucao_porcentagem,
        'Dispersao_KM': media_dispersao_km,
        'Rating': media_rating,
        'Reposicao_Valor': f"{soma_reposicao:.2f}".replace('.', ','),
        'Refugo_Porcentagem': media_refugo
    }

    return render_template(
        'painel_supervisor.html',
        funcionarios=funcionarios,
        indicadores=dados_formatados,
        mensagem=mensagem,
        medias=medias
    )





@app.route('/explicacoes')
def explicacoes():
    if 'id_motorista' not in session:
        return redirect(url_for('login'))
    return render_template('explicacoes.html')

@app.route('/observacao', methods=['POST'])
def observacao():
    if 'id_motorista' not in session:
        return redirect(url_for('login'))

    texto = request.form.get('observacao', '').strip()
    id_motorista = session['id_motorista']

    if texto:
        conexao = conectar_banco()
        if conexao:
            cursor = conexao.cursor(as_dict=True)
            try:
                cursor.execute("INSERT INTO Observacoes (ID_Motorista, Texto) VALUES (%s, %s)", (id_motorista, texto))
                conexao.commit()
            except Exception as e:
                print("Erro ao salvar observação:", e)
            finally:
                cursor.close()
                conexao.close()

    return redirect(url_for('painel'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
