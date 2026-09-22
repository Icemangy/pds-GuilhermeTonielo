import sqlite3
from flask import Flask, jsonify, request

app = Flask(__name__)
BANCO = "petshop.db"

def conectar():
    return sqlite3.connect(BANCO)

# ---------------------------------------------------------------
# ROTAS DE DONOS - CODIGO DE REFERENCIA
# ---------------------------------------------------------------
@app.route("/donos", methods=["GET"])
def listar_donos():
    conexao = conectar()
    cursor = conexao.cursor()
    cursor.execute("SELECT id, nome, telefone FROM donos")
    linhas = cursor.fetchall()
    conexao.close()
    
    donos = []
    for linha in linhas:
        donos.append({
            "id": linha[0],
            "nome": linha[1],
            "telefone": linha[2]
        })
    return jsonify(donos)

@app.route("/donos/<int:dono_id>", methods=["GET"])
def buscar_dono(dono_id):
    conexao = conectar()
    cursor = conexao.cursor()
    cursor.execute(
        "SELECT id, nome, telefone FROM donos WHERE id = ?", (dono_id,)
    )
    linha = cursor.fetchone()
    conexao.close()
    
    if linha is None:
        return jsonify({"erro": "Dono nao encontrado"}), 404
        
    dono = {
        "id": linha[0],
        "nome": linha[1],
        "telefone": linha[2]
    }
    return jsonify(dono)

@app.route("/donos", methods=["POST"])
def criar_dono():
    dados = request.json
    if not dados or "nome" not in dados or "telefone" not in dados:
        return jsonify({"erro": "Informe nome e telefone"}), 400
        
    conexao = conectar()
    cursor = conexao.cursor()
    cursor.execute(
        "INSERT INTO donos (nome, telefone) VALUES (?, ?)", (dados["nome"], dados["telefone"])
    )
    conexao.commit()
    novo_id = cursor.lastrowid
    conexao.close()
    
    dono = {
        "id": novo_id,
        "nome": dados["nome"],
        "telefone": dados["telefone"]
    }
    return jsonify(dono), 201

@app.route("/donos/<int:dono_id>", methods=["PUT"])
def atualizar_dono(dono_id):
    dados = request.json
    if not dados or "nome" not in dados or "telefone" not in dados:
        return jsonify({"erro": "Informe nome e telefone"}), 400
        
    conexao = conectar()
    cursor = conexao.cursor()
    cursor.execute(
        "UPDATE donos SET nome = ?, telefone = ? WHERE id = ?", (dados["nome"], dados["telefone"], dono_id)
    )
    conexao.commit()
    alterados = cursor.rowcount
    conexao.close()
    
    if alterados == 0:
        return jsonify({"erro": "Dono nao encontrado"}), 404
        
    dono = {
        "id": dono_id,
        "nome": dados["nome"],
        "telefone": dados["telefone"]
    }
    return jsonify(dono)

@app.route("/donos/<int:dono_id>", methods=["DELETE"])
def remover_dono(dono_id):
    conexao = conectar()
    cursor = conexao.cursor()
    cursor.execute("DELETE FROM donos WHERE id = ?", (dono_id,))
    conexao.commit()
    removidos = cursor.rowcount
    conexao.close()
    
    if removidos == 0:
        return jsonify({"erro": "Dono nao encontrado"}), 404
        
    return jsonify({"mensagem": "Dono removido com sucesso"})

# ---------------------------------------------------------------
# ROTAS DE PETS - SUA PARTE (IMPLEMENTADA)
# ---------------------------------------------------------------

# 1. GET /pets - Lista todos os pets com o nome do dono e filtro opcional
@app.route("/pets", methods=["GET"])
def listar_pets():
    conexao = conectar()
    cursor = conexao.cursor()
    
    # Captura o filtro opcional ?dono_id= da URL
    dono_id = request.args.get("dono_id")
    
    # Query base utilizando JOIN para buscar dados do pet e o nome do dono correspondente
    query = """
        SELECT p.id, p.nome, p.especie, p.dono_id, d.nome 
        FROM pets p
        JOIN donos d ON p.dono_id = d.id
    """
    
    if dono_id:
        query += " WHERE p.dono_id = ?"
        cursor.execute(query, (dono_id,))
    else:
        cursor.execute(query)
        
    linhas = cursor.fetchall()
    conexao.close()
    
    pets = []
    for linha in linhas:
        pets.append({
            "id": linha[0],
            "nome": linha[1],
            "especie": linha[2],
            "dono_id": linha[3],
            "nome_dono": linha[4]
        })
    return jsonify(pets)

# 2. GET /pets/<id> - Busca um pet pelo id
@app.route("/pets/<int:pet_id>", methods=["GET"])
def buscar_pet(pet_id):
    conexao = conectar()
    cursor = conexao.cursor()
    cursor.execute(
        "SELECT id, nome, especie, dono_id FROM pets WHERE id = ?", (pet_id,)
    )
    linha = cursor.fetchone()
    conexao.close()
    
    if linha is None:
        return jsonify({"erro": "Pet nao encontrado"}), 404
        
    pet = {
        "id": linha[0],
        "nome": linha[1],
        "especie": linha[2],
        "dono_id": linha[3]
    }
    return jsonify(pet)

# 3. POST /pets - Cadastra um novo pet
@app.route("/pets", methods=["POST"])
def criar_pet():
    dados = request.json
    if not dados or "nome" not in dados or "especie" not in dados or "dono_id" not in dados:
        return jsonify({"erro": "Informe nome, especie e dono_id"}), 400
        
    conexao = conectar()
    cursor = conexao.cursor()
    
    # Validação opcional: Garante que o dono realmente existe antes de associar o pet
    cursor.execute("SELECT id FROM donos WHERE id = ?", (dados["dono_id"],))
    if cursor.fetchone() is None:
        conexao.close()
        return jsonify({"erro": "Dono informado nao existe"}), 400

    cursor.execute(
        "INSERT INTO pets (nome, especie, dono_id) VALUES (?, ?, ?)", 
        (dados["nome"], dados["especie"], dados["dono_id"])
    )
    conexao.commit()
    novo_id = cursor.lastrowid
    conexao.close()
    
    pet = {
        "id": novo_id,
        "nome": dados["nome"],
        "especie": dados["especie"],
        "dono_id": dados["dono_id"]
    }
    return jsonify(pet), 201

# 4. PUT /pets/<id> - Atualiza um pet
@app.route("/pets/<int:pet_id>", methods=["PUT"])
def atualizar_pet(pet_id):
    dados = request.json
    if not dados or "nome" not in dados or "especie" not in dados or "dono_id" not in dados:
        return jsonify({"erro": "Informe nome, especie e dono_id"}), 400
        
    conexao = conectar()
    cursor = conexao.cursor()
    
    # Validação opcional: Garante que o novo dono informado existe
    cursor.execute("SELECT id FROM donos WHERE id = ?", (dados["dono_id"],))
    if cursor.fetchone() is None:
        conexao.close()
        return jsonify({"erro": "Dono informado nao existe"}), 400

    cursor.execute(
        "UPDATE pets SET nome = ?, especie = ?, dono_id = ? WHERE id = ?", 
        (dados["nome"], dados["especie"], dados["dono_id"], pet_id)
    )
    conexao.commit()
    alterados = cursor.rowcount
    conexao.close()
    
    if alterados == 0:
        return jsonify({"erro": "Pet nao encontrado"}), 404
        
    pet = {
        "id": pet_id,
        "nome": dados["nome"],
        "especie": dados["especie"],
        "dono_id": dados["dono_id"]
    }
    return jsonify(pet)

# 5. DELETE /pets/<id> - Remove um pet
@app.route("/pets/<int:pet_id>", methods=["DELETE"])
def remover_pet(pet_id):
    conexao = conectar()
    cursor = conexao.cursor()
    cursor.execute("DELETE FROM pets WHERE id = ?", (pet_id,))
    conexao.commit()
    removidos = cursor.rowcount
    conexao.close()
    
    if removidos == 0:
        return jsonify({"erro": "Pet nao encontrado"}), 404
        
    return jsonify({"mensagem": "Pet removido com sucesso"})

if __name__ == "__main__":
    app.run(debug=True)
