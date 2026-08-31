# 失落之地

玩家执政一块北美地盘。世界按事件走，模型只做首席顾问。

## 玩法

解压 Release 里的 zip，安装 Python 依赖后双击 `play.bat`：

```
pip install -r requirements.txt
play.bat
```

浏览器打开 http://127.0.0.1:8010 。

从源码克隆的，还要构建前端（zip 里已经带上了，不用这一步）：

```
cd src/frontend
npm install
npm run build
```
