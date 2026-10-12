from app import app, db, Dono, Pet


def criar_banco():
    """Cria as tabelas e adiciona exemplos somente se nao houver donos."""
    with app.app_context():
        db.create_all()

        if Dono.query.first() is not None:
            print("Banco ja possui dados. Nenhum registro foi alterado.")
            return

        ana = Dono(nome="Ana Paula Ribeiro", telefone="45999110001")
        bruno = Dono(nome="Bruno Cardoso", telefone="45999110002")
        carla = Dono(nome="Carla Meneghel", telefone="45999110003")

        donos = [ana, bruno, carla]
        pets = [
            Pet(nome="Rex", especie="cachorro", idade=4, dono=ana),
            Pet(nome="Mimi", especie="gato", idade=2, dono=ana),
            Pet(nome="Thor", especie="cachorro", idade=7, dono=bruno),
            Pet(nome="Nina", especie="gato", idade=1, dono=carla),
            Pet(nome="Pingo", especie="passaro", idade=3, dono=carla),
        ]

        db.session.add_all(donos + pets)
        db.session.commit()
        print("Banco criado com sucesso.")
        print(f"Foram inseridos {len(donos)} donos e {len(pets)} pets.")


if __name__ == "__main__":
    criar_banco()
