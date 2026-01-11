import os
import json
import hashlib
from datetime import datetime
import config


def ensureOutputDir():
    if not os.path.exists(config.OUTPUT_DIR):
        os.makedirs(config.OUTPUT_DIR)


def generateModFilename(modId):
    return os.path.join(config.OUTPUT_DIR, f"mod_{modId}.json")


def saveModToJson(modData):
    ensureOutputDir()
    filename = generateModFilename(modData['mod_id'])
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(modData, f, indent=2, ensure_ascii=False)
    return filename


def modExists(modId):
    filename = generateModFilename(modId)
    return os.path.exists(filename)


def loadModFromJson(modId):
    filename = generateModFilename(modId)
    if not os.path.exists(filename):
        return None
    with open(filename, 'r', encoding='utf-8') as f:
        return json.load(f)


def generateContentHash(modData):
    content = json.dumps(modData, sort_keys=True)
    return hashlib.md5(content.encode()).hexdigest()


def formatTimestamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def cleanText(text):
    if not text:
        return ""
    return text.strip()