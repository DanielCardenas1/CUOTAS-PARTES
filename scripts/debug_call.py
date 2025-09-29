import subprocess
cmd = ['python', 'generar_pdf_oficial.py', '--id', '26489799', '--periodo', 'custom', '--año-inicio', '2022', '--mes-inicio', '9']
proc = subprocess.run(cmd, capture_output=True, text=True)
print('RETURN CODE:', proc.returncode)
print('STDOUT REPR:')
print(repr(proc.stdout))
print('\nSTDERR REPR:')
print(repr(proc.stderr))
