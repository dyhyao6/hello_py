class Solution:
    def lengthOfLongestSubstring(self, s: str) -> int:
        """
        给定一个字符串 s ，请你找出其中不含有重复字符的 最长 子串 的长度。
        示例 1:
        输入: s = "abcabcbb"
        输出: 3
        解释: 因为无重复字符的最长子串是 "abc"，所以其长度为 3。注意 "bca" 和 "cab" 也是正确答案。
        示例 2:
        输入: s = "bbbbb"
        输出: 1
        解释: 因为无重复字符的最长子串是 "b"，所以其长度为 1
        :param s:
        :return:
        """
        char_index = {}
        max_len = 0
        start = 0
        for end, ch in enumerate(s):
            if ch in char_index and char_index[ch] >= start:
                start = char_index[ch] + 1
            char_index[ch] = end
            max_len = max(max_len, end - start + 1)

        return max_len

    def longestPalindrome(self, s: str) -> str:
        """
        给你一个字符串 s，找到 s 中最长的 回文 子串。
        示例 1：
        输入：s = "babad"
        输出："bab"
        解释："aba" 同样是符合题意的答案。
        示例 2：
        输入：s = "cbbd"
        输出："bb"
        :param s:
        :return:
        """
        if len(s) < 2:
            return s
        left, right = 0, 0

        def expand(left, right):
            while left >= 0 and right < len(s) and s[left] == s[right]:
                left -= 1
                right += 1
            return left + 1, right - 1

        for i in range(len(s)):
            l1, r1 = expand(i, i)
            l2, r2 = expand(i, i + 1)
            if r1 - l1 > right - left:
                left, right = l1, r1
            if r2 - l2 > right - left:
                left, right = l2, r2
        return s[left:right + 1]

    def convert(self, s: str, numRows: int) -> str:
        """
        将一个给定字符串 s 根据给定的行数 numRows ，以从上往下、从左到右进行 Z 字形排列。
        比如输入字符串为 "PAYPALISHIRING" 行数为 3 时，排列如下：
        P   A   H   N
        A P L S I I G
        Y   I   R
        之后，你的输出需要从左往右逐行读取，产生出一个新的字符串，比如："PAHNAPLSIIGYIR"。

        :param s:
        :param numRows:
        :return:
        """
        # 特殊情况：只有一行时，直接返回原字符串
        if numRows == 1 or numRows >= len(s):
            return s

        # 创建每一行的字符串容器
        rows = [""] * numRows

        row = 0  # 当前所在行
        direction = 1  # 1 表示向下，-1 表示向上

        # 遍历每个字符
        for char in s:
            rows[row] += char

            # 到达顶部或底部后改变方向
            if row == 0:
                direction = 1
            elif row == numRows - 1:
                direction = -1

            # 移动到下一行
            row += direction

        # 拼接所有行
        return "".join(rows)

    def isValid(self, s: str) -> bool:
        stack = []
        mapping = {')': '(', ']': '[', '}': '{'}
        for ch in s:
            if ch in mapping:
                top_elem = stack.pop() if stack else '#'
                if mapping[ch] != top_elem:
                    return False
            else:
                stack.append(ch)
        return not stack

    def strStr(self, haystack: str, needle: str) -> int:
        """
        给你两个字符串 haystack 和 needle ，请你在 haystack 字符串中找出 needle 字符串的第一个匹配项的下标（下标从 0 开始）。
        如果 needle 不是 haystack 的一部分，则返回  -1 。
         示例 1：
         输入：haystack = "sadbutsad", needle = "sad"
         输出：0
         解释："sad" 在下标 0 和 6 处匹配。
         第一个匹配项的下标是 0 ，所以返回 0 。
         示例 2：
         输入：haystack = "leetcode", needle = "leeto"
         输出：-1
         解释："leeto" 没有在 "leetcode" 中出现，所以返回 -1
        :param haystack:
        :param needle:
        :return:
        """
        if not needle:
            return 0
        n, m = len(haystack), len(needle)
        for i in range(n - m + 1):
            if haystack[i:i + m] == needle:
                return i
        return -1

    def addBinary(self, a: str, b: str) -> str:
        """
        给你两个二进制字符串 a 和 b ，以二进制字符串的形式返回它们的和。
        示例 1：
        输入:a = "11", b = "1"
        输出："100"
        示例 2：
        输入：a = "1010", b = "1011"
        输出："10101"
        :param a:
        :param b:
        :return:
        """
        i, j = len(a) - 1, len(b) - 1
        carry = 0
        result = []
        while i >= 0 or j >= 0 or carry:
            total = carry
            if i >= 0:
                total += int(a[i])
                i -= 1
            if j >= 0:
                total += int(b[j])
                j -= 1
            result.append(str(total % 2))
            carry = total // 2
        return ''.join(reversed(result))


if __name__ == '__main__':
    s = Solution()
    # print(s.lengthOfLongestSubstring('bbbbbbb'))
    # print(s.longestPalindrome('cbbd'))

    print(s.convert("PAYPALISHIRING", 3))  # PAHNAPLSIIGYIR

    print(s.isValid("()[]{}"))  # True
