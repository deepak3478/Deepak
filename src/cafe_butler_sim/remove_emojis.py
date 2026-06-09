import os
import glob
import re

def remove_emojis():
    # Emojis and special characters to replace
    replacements = {
        '⚠': '[WARNING]',
        '❌': '[ERROR]',
        '📦': '[ORDER]',
        '✅': '[SUCCESS]',
        '🛑': '[CANCEL]',
        '▶': '[START]',
        '⏱': '[TIMEOUT]',
        '✔': '[DONE]',
        '🚫': '[SKIP]',
        '🚗': '[MOVE]',
        '⌛': '[WAIT]',
        '📤': '[SEND]',
        '→': '->',
        '…': '...'
    }
    
    search_pattern = os.path.join('/home/deepak33/Desktop/KKR_TASKS/coffee_shop_ws/src/cafe_butler_sim/cafe_butler_sim', '*.py')
    files = glob.glob(search_pattern)
    
    for file_path in files:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        modified = False
        for emoji, replacement in replacements.items():
            if emoji in content:
                content = content.replace(emoji, replacement)
                modified = True
                
        # Also let's just strip any other potential emojis using a regex for high surrogate blocks
        # Actually replacing specific ones is safer to not break code.
        
        if modified:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"Updated {file_path}")

if __name__ == '__main__':
    remove_emojis()
