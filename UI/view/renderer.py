class BoardRenderer:
    def render(self, snapshot):
        return "\n".join(" ".join(row) for row in snapshot.grid)
