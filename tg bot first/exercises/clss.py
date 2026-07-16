class Stydent():
    def __init__(self,name,house,grade):
        self.name =             name
        self.house = house
        self.grade = grade
    def limit(self,grade):
        if grade < 0 or grade > 12:
            raise ValueError("incorrect grade")
        else:
            return self.grade
    def get_grade(self):
        self.grade = int(input("Print your grade: "))
        self.limit(self.grade)
        return self.grade
    def __str__(self):
        return f"name: {self.name} house: {self.house} grade: {self.grade}"
        
        
        
        
s = Stydent("Mark","C",grade = None)
s.get_grade()
print(s)