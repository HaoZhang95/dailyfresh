# dailyfresh

## Fastdfs在Centos安装教程(1)和(2)
###https://www.codetd.com/article/1815445
###https://blog.csdn.net/MissEel/article/details/80859865

## 在进行教程(2d的过程中如果遇到下列错误的解决方法
###/usr/include/fastdfs/fdfs_define.h:15:27: fatal error: common_define.h: No such file or directory
###暴力直接的方法就是 把 /usr/include/fastcommon 下面的文件，复制一份到 /usr/include/fastdfs 再进行编译