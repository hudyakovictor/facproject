from server.registry import metric
@metric("iris_width_ratio","Радужка / ширина глазной щели",model="mediapipe",unit="ratio",inputs=("iris_measurements",))
def f(ctx):return ctx["iris_measurements"]["iris_width_ratio"]
