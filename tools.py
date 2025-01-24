import os
script_dir = os.path.dirname(os.path.abspath(__file__))

def save_text(text, path='temp0.txt'):
    file_path = os.path.join(os.path.dirname(__file__), path)
    directory = os.path.dirname(file_path)
    if not os.path.exists(directory):
        os.makedirs(directory)
    with open(file_path, 'w', encoding='utf-8') as file:
        file.write(text)
    print(f"Saved to {path} successfully")