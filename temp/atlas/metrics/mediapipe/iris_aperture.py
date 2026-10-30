from server.registry import metric
@metric("iris_height_ratio","Радужка / высота глазной щели",model="mediapipe",unit="ratio",inputs=("iris_measurements",))
def f(ctx):return ctx["iris_measurements"]["iris_height_ratio"]
