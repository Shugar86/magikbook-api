class EloService:
    @staticmethod
    def calculate_new_ratings(
        rating_winner: int, rating_loser: int, k_factor: int = 32
    ) -> tuple[int, int]:
        """Calculates new Elo ratings for a winner and loser."""
        expected_winner = 1 / (1 + 10 ** ((rating_loser - rating_winner) / 400))
        expected_loser = 1 / (1 + 10 ** ((rating_winner - rating_loser) / 400))

        new_rating_winner = round(rating_winner + k_factor * (1 - expected_winner))
        new_rating_loser = round(rating_loser + k_factor * (0 - expected_loser))

        return new_rating_winner, new_rating_loser
