import getpass
from passlib.context import CryptContext

# Use the same context as in the application
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def main():
    password = getpass.getpass("Enter password to hash: ")
    hashed_password = pwd_context.hash(password)
    print("\nYour hashed password is:\n")
    print(hashed_password)

if __name__ == "__main__":
    main()