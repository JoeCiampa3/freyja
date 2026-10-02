import gspread
from google.oauth2.service_account import Credentials
from string import Template
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
creds = Credentials.from_service_account_file(r"c:\Users\Joe\Desktop\Project Valkyrie\Misc\project-valkyrie-509701-0b68d6f5e84d.json", scopes=SCOPES)
gc = gspread.authorize(creds)

def read_table(sh, name, key_header):
    resp = sh.values_get(name, params={"valueRenderOption": "UNFORMATTED_VALUE"})
    rows = resp["values"]
    header = [str(h).strip() for h in rows[0]]
    body = rows[1:]
    key_col = header.index(key_header)

    tab_data = []
    for row in body:
        if len(row) <= key_col or str(row[key_col]).strip() == "":
            continue
        row_dict = {}
        for i, label in enumerate(header):
            if label == "":
                continue
            row_dict[label] = row[i] if i < len(row) else ""
        tab_data.append(row_dict)
    return tab_data

def build_params():
    
 
def load_params(sh):
    bsip_rows = read_table(sh, "bsip", "Segment")
    params = {ident(r["segment"])}

    segments = []
    for row in body:
        if len(row) <= seg_col:
            continue
        cell = ident(row[seg_col])
        if cell == "":
            continue
        segments.append(cell)

    if len(segments) != len(set(segments)):
        raise SystemExit(f"Duplicate segments: {segments}")
    if set(segments) != set(expected_segments):
        raise SystemExit(f"Sheet drift. Expected: {expected_segments} Received: {segments}. Check recent sheet edits vs code.")

    params = {}
    for row in body:
        if len(row) <= seg_col or str(row[seg_col]).strip() == "":
            continue
        seg = ident(row[seg_col])
        params[seg] = {}
        for i, col_name in enumerate(header):
            if col_name.lower() == "segment":
                continue
            if i < len(row) and row[i] != "":
                params[seg][col_name.split(" ", 1)[0].lower()] = row[i]

    params = mirror(params)  #mirrors bilateral segments before params is returned

    return params   #full 16 elements including bilateral

def mirror(params):
    out = {}
    for seg, p in params.items():
        if seg in BILATERAL:
            out[f"{seg}_right"] = dict(p)
            out[f"{seg}_left"]  = {k: (-v if k in FLIP_Y else v) for k, v in p.items()}
        else:
            out[seg] = p
    return out

def fmt(v): #removes -0.0 ambiguity
    x = float(v)
    if x == 0.0:
        x = 0.0
    return f"{x:.12g}"

def load_template(path):
    return Template(path.read_text(encoding="utf-8"))

def render(tmpl, params):
    flat = {f"{seg}_{key}": fmt(val)
            for seg, p in params.items()
            for key, val in p.items()}
    return tmpl.substitute(flat)

def ident(name):
    return re.sub(r"\W+", "_", str(name).strip().lower()).strip("_")


expected_segments = ["head_neck", "thorax", "abdomen", "pelvis", "upper_arm", "forearm", "hand", "thigh", "shank", "foot"]
BILATERAL = ["upper_arm", "forearm", "hand", "thigh", "shank", "foot"]
expected_bsips = ["mass", "length", "com_x", "com_y", "com_z", "ixx", "iyy", "izz", "ixy", "ixz", "iyz"]
FLIP_Y = ["com_y", "ixy", "iyz"]


def main():
    sh = gc.open_by_key("16-XKTGIO4FvCfACWS000RBR2BNFJ0ho6tvMeRswaV2Y")
    sheet = sh.worksheet("MuJoCo Reference")
    bsip = load_params(sh)
    tmpl = load_template(ROOT / "models" / "freyja_template.xml")
    xml = render(tmpl, bsip)
    (ROOT / "models" / "freyja.xml").write_text(xml, encoding="utf-8")
    print(read_table(sh, "bsip", "Segment"))


if __name__ == "__main__":
    main()