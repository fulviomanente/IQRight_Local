from cryptography.fernet import Fernet

# Generate a secure key
key = Fernet.generate_key()

# Save the key to the key file
with open('full_load.iqr.key', 'wb') as key_file:
    key_file.write(key)

print("Encryption key has been generated and saved to full_load.iqr.key") 