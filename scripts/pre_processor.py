import gspread
from google.oauth2.service_account import Credentials
from string import Template 

SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
creds = Credentials.from_service_account_file(r"c:\Users\Joe\Desktop\Project Valkyrie\Misc\project-valkyrie-509701-0b68d6f5e84d.json", scopes=SCOPES)
gc = gspread.authorize(creds)

sheet = gc.open_by_key("16-XKTGIO4FvCfACWS000RBR2BNFJ0ho6tvMeRswaV2Y").worksheet("MuJoCo Reference")

Ixx = sheet.acell("F15").value

segments = ["head_and_neck", "thorax", "abdoment", "pelvis", "upper_arm", "forearm", "hand", "thigh", "shank", "foot"]
bsips = ["mass", "length", "com_x", "com_y", "com_z", "ixx", "iyy", "izz", "ixz", "iyz"]
segment_bsips = {}

bsip_index = 0
seg_index = 0 #segment index, incremented after a dicitonary value is added to segments_bsip, never reset
index = 0 #bsip index, reset every row because each segment needs its own complete dictionary of bsip data
for i in range(15, 25):
    row = sheet.row_values(i)
    row_bsips = {}
    subset = row[1 : 11]
    for cell in subset:
        row_bsips[bsips[bsip_index]] = float(cell)
        if bsip_index == len(bsips) - 1:
            break 
        else:
            bsip_index += 1
    segment_bsips[segments[seg_index]] = row_bsips
    if seg_index == len(segments) - 1:
        break
    else:
        seg_index += 1
    bsip_index = 0

print(segment_bsips)