import numpy as np
import matplotlib.pyplot as plt

# 设置均值和标准差
mu = 0  # 均值
sigma = 2  # 标准差
delta = 5
# 生成一些数据点
x = np.linspace(mu - delta*sigma, mu + delta*sigma, 1500)  # 生成100个数据点，范围为均值加减2倍标准差
y = list((1/(sigma * np.sqrt(2 * np.pi))) * np.exp(-0.5 * ((x - mu)/sigma)**2)+0.05)  # 正态分布函数
split = 300
a = y[split::]
b = y[:split:]
a.extend(b)
print(np.mean(a))
# print(y[750])
# 绘制曲线
plt.plot(x, a)

# 添加标题和标签
plt.title('正态分布函数曲线')
plt.xlabel('x')
plt.ylabel('y')

# 显示图形
plt.show()


