class CriteriaValidator:
    
    @staticmethod
    def validate(scores: dict, criteria: list):

        expected = {c.name for c in criteria}

        actual = set(scores.keys())

        if expected != actual:

            missing = expected - actual
            extra = actual - expected

            raise ValueError(
                f"Ошибка критериев оценки. "
                f"Отсутствуют критерии: {missing}. "
                f"Лишние критерии: {extra}"
            )

        for criterion, score in scores.items():

            if not isinstance(score, int):
                raise ValueError(
                    f"Критерий '{criterion}' должен иметь целое значение"
                )

            if score < 1 or score > 5:
                raise ValueError(
                    f"Оценка по критерию '{criterion}' должна быть от 1 до 5"
                )
