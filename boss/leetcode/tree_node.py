import datetime
import time


class Node:
    def __init__(self, val, left=None, right=None):
        self.val = val
        self.left = left
        self.right = right

    def lookup(self, val, parent=None):
        if self.val < val:
            if self.right is None:
                return None, parent
            return self.right.lookup(val, self)
        elif self.val > val:
            if self.left is None:
                return None, parent
            return self.left.lookup(val, self)
        else:
            return self, parent

    def mid_travel(self):
        """
        中序遍历
        :return:
        """
        if self.left is not None:
            self.left.mid_travel()
        print(self.val)
        if self.right is not None:
            self.right.mid_travel()

    def pre_travel(self):
        """
        前序遍历
        :return:
        """
        print(self.val)
        if self.left is not None:
            self.left.pre_travel()
        if self.right is not None:
            self.right.pre_travel()

    def post_travel(self):
        """
        后序遍历
        :return:
        """
        if self.left is not None:
            self.left.post_travel()
        if self.right is not None:
            self.right.post_travel()
        print(self.val)

    def __str__(self):
        lines, *_ = self._display_aux()
        return "\n".join(lines)

    def _display_aux(self):
        """返回一组字符串，表示倒置树的横向图形"""
        # 没有子节点
        if self.left is None and self.right is None:
            line = str(self.val)
            width = len(line)
            height = 1
            middle = width // 2
            return [line], width, height, middle

        # 只有左子树
        if self.right is None:
            lines, n, p, x = self.left._display_aux()
            s = str(self.val)
            u = len(s)
            first_line = (x + 1) * " " + (n - x - 1) * "_" + s
            second_line = x * " " + "/" + (n - x - 1 + u) * " "
            shifted_lines = [line + u * " " for line in lines]
            return [first_line, second_line] + shifted_lines, n + u, p + 2, n + u // 2

        # 只有右子树
        if self.left is None:
            lines, n, p, x = self.right._display_aux()
            s = str(self.val)
            u = len(s)
            first_line = s + x * "_" + (n - x) * " "
            second_line = (u + x) * " " + "\\" + (n - x - 1) * " "
            shifted_lines = [u * " " + line for line in lines]
            return [first_line, second_line] + shifted_lines, n + u, p + 2, u // 2

        # 有左右子树
        left, n, p, x = self.left._display_aux()
        right, m, q, y = self.right._display_aux()
        s = str(self.val)
        u = len(s)
        first_line = (x + 1) * " " + (n - x - 1) * "_" + s + y * "_" + (m - y) * " "
        second_line = x * " " + "/" + (n - x - 1 + u + y) * " " + "\\" + (m - y - 1) * " "
        if p < q:
            left += [" " * n] * (q - p)
        elif q < p:
            right += [" " * m] * (p - q)
        zipped_lines = zip(left, right)
        lines = [first_line, second_line] + [a + u * " " + b for a, b in zipped_lines]
        return lines, n + m + u, max(p, q) + 2, n + u // 2

    def max_deep(self, root):
        """
        二叉树最大深度
        :return:
        """
        return max(self.max_deep(root.left), self.max_deep(root.right)) + 1 if root else 0

    def is_same_tree(self, p, q):
        """
        相同的树
        :param p:
        :param q:
        :return:
        """
        if not p and not q:
            return True
        elif not p or not q:
            return False
        elif p.val != q.val:
            return False
        else:
            return self.is_same_tree(p.left, q.left) and self.is_same_tree(p.right, q.right)


if __name__ == """__main__""":
    # tree = Node(1, Node(3, Node(7, Node(0)), Node(6)), Node(2, Node(5), Node(4)))
    # print(tree.__str__())
    from datetime import datetime, timezone
    import time

    ts = time.time()
    dt_utc = datetime.fromtimestamp(ts, tz=timezone.utc)
    print(dt_utc)
    print(type(dt_utc))
