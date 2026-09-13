content = open('app/models.py', 'r', encoding='utf-8').read()
marker = "    predictions = db.relationship('YieldPrediction', backref='crop_info', lazy='dynamic')\n"
addition = "    pest_traps = db.relationship('PestTrap', backref='crop_trap_info', lazy='dynamic')\n"
if 'pest_traps' not in content:
    content = content.replace(marker, marker + addition, 1)
    open('app/models.py', 'w', encoding='utf-8').write(content)
    print("Done: pest_traps added")
else:
    print("Already present")
