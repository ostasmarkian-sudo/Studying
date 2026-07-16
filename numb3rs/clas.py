class Animals:
    def __init__(self,name,house):
        if not name:
            raise ValueError
        self.name = name
        self.house = house
    def __str__(self):
        return f"{self.name} from {self.house}"
name = input("name")
house = input("House")
animal = Animals(name, house)
print(animal)
        
        
        


