class EvolutionException(Exception):
    def __init__(self,value):
        self.value=value

    def __str__(self):
        return str(self.value)
        
class CannotSimulate(Exception):
    pass
    
class SimulationFailure(Exception):
    def __init__(self, diff):
        self.diff = diff
    