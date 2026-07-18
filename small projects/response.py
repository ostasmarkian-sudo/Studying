import re
email  = input("What's your email address?: ").strip()
res = r"^[a-z0-9_%+-]{5,63}@[a-z0-9]{1,63}\.[a-z]{1,63}$"
if result := re.fullmatch(res , email , re.IGNORECASE):
    print("correct")
else:
    print("Invalid email format")
