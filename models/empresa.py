import json 
import os

def load_empresas():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    ruta = os.path.join(base_dir,"..", "data", "empresas.json")
    with open(ruta, "r", encoding="utf-8") as f:
        return json.load(f)
    
def get_empresa_by_numer(numero):
    empresas = load_empresas()
    for e in empresas:
        if e["numero"] == numero:
            return e
    return None

